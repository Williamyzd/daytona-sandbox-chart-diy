# 修复 OIDC 自签名证书问题

## 需求场景
Daytona API 服务在尝试从 Dex OpenID issuer 获取配置时遇到 "Failed to fetch OpenID configuration: self-signed certificate" 错误。这导致 OIDC 认证流程失败，用户无法正常登录。cert-manager 已经安装。

## 根本原因分析
1. Dex 服务当前使用自签名证书 (`selfSigned: true`)
2. API 服务需要通过 HTTPS 连接到 Dex (https://dex.sandbox.ze-dong.cn/dex)
3. 自签名证书不受信任，导致 TLS 握手失败
4. 虽然 API 的 `NODE_TLS_REJECT_UNAUTHORIZED` 环境变量设置为 "0"，但某些 HTTP 客户端可能不遵循此全局设置
5. **关键信息**：cert-manager 已安装，可以使用 cert-manager 颁发受信任的证书

## 架构技术方案
考虑到 cert-manager 已安装，采用以下更安全且优雅的方案：

**方案：使用 cert-manager 颁发受信任的证书**
1. **保留现有Issuer**：继续使用 `selfsigned-issuer` (已在 charts/cert.yaml 中定义)
2. **确保证书Secret正确**：确认 `sandbox.ze-dong.cn-tls` Secret 包含正确的证书
3. **配置API信任证书**：确保 API 服务能够访问并信任该证书
4. **移除不安全配置**：移除 `NODE_TLS_REJECT_UNAUTHORIZED: "0"` 恢复正常的证书验证

## 影响文件
- **修改类型**：配置优化
- **主要文件**：
  - `charts/daytona/values.yaml` - 环境变量和证书配置
  - `charts/cert.yaml` - cert-manager Issuer 和 Certificate 配置（可能需要调整）
  - `charts/daytona/templates/api-deployment.yaml` - API 部署模板（可能需要调整）
- **影响组件**：
  - API Deployment (daytona-api)
  - Dex Ingress
  - API Ingress
  - Proxy Ingress
- **影响功能**：OIDC 认证流程、所有 HTTPS 连接

## 实现细节

### 步骤 1：验证 cert-manager 配置
确认 charts/cert.yaml 中的 Issuer 和 Certificate 配置正确：
```yaml
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: selfsigned-issuer
  namespace: default
spec:
  selfSigned: {}

---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: "sandbox.ze-dong.cn-tls"
  namespace: default
spec:
  secretName: "sandbox.ze-dong.cn-tls"
  duration: 2160h  # 90 天
  renewBefore: 360h  # 提前 15 天续签
  commonName: "sandbox.ze-dong.cn"
  dnsNames:
  - "sandbox.ze-dong.cn"
  - "*.sandbox.ze-dong.cn"  # 包括 dex.sandbox.ze-dong.cn
  issuerRef:
    name: selfsigned-issuer
    kind: Issuer
```

### 步骤 2：配置 API 信任证书
修改 `charts/daytona/values.yaml`，移除不安全的配置，添加证书信任：

```yaml
services:
  api:
    env:
      # 移除不安全的全局禁用证书验证
      # NODE_TLS_REJECT_UNAUTHORIZED: "0"  # 删除此行
      
      # 添加：配置 Node.js 信任特定的 CA 证书
      NODE_EXTRA_CA_CERTS: "/etc/ssl/certs/dex-ca.crt"
    
    # 挂载证书到容器
    extraVolumeMounts:
      - name: dex-tls-secret
        mountPath: /etc/ssl/certs/dex-ca.crt
        subPath: ca.crt
        readOnly: true
    
    extraVolumes:
      - name: dex-tls-secret
        secret:
          secretName: "sandbox.ze-dong.cn-tls"
          items:
            - key: ca.crt  # Certificate 资源会生成 ca.crt
              path: ca.crt
```

### 步骤 3：修改 API 部署模板（如果需要）
如果 values.yaml 的 extraVolumes 不会被正确应用，需要修改 `charts/daytona/templates/api-deployment.yaml`，在 spec.template.spec.volumes 中添加：

```yaml
{{- if .Values.dex.enabled }}
- name: dex-tls-secret
  secret:
    secretName: {{ .Values.dex.ingress.tlsSecretName | default (printf "%s-tls" .Values.baseDomain) }}
    items:
      - key: ca.crt
        path: dex-ca.crt
{{- end }}
```

并在容器的 volumeMounts 中添加：

```yaml
{{- if .Values.dex.enabled }}
- name: dex-tls-secret
  mountPath: /etc/ssl/certs/dex-ca.crt
  subPath: dex-ca.crt
  readOnly: true
{{- end }}
```

### 步骤 4：确保环境变量正确
确认 `NODE_EXTRA_CA_CERTS` 环境变量正确注入到 API 容器中。

## 边界条件与异常处理
1. **证书Secret存在性**：确保 `sandbox.ze-dong.cn-tls` Secret 已经由 cert-manager 创建
2. **CA证书提取**：自签名证书的 Secret 可能不包含 ca.crt，需要从 tls.crt 中提取
3. **证书续签**：cert-manager 会自动续签，新的 CA 证书需要被 Pod 重新加载（可能需要重启）
4. **多服务共享**：API、Proxy、Dex 都使用同一个证书，配置应该一致
5. **命名空间**：确保所有服务在同一个命名空间，或者使用全局 ClusterIssuer

## 数据流动路径
1. cert-manager 创建 Certificate 资源 → 生成证书和私钥 → 存储到 Secret
2. API Pod 启动 → 挂载 Secret 中的证书到 `/etc/ssl/certs/dex-ca.crt`
3. 环境变量 `NODE_EXTRA_CA_CERTS=/etc/ssl/certs/dex-ca.crt` 生效
4. API 发起 OIDC 请求到 https://dex.sandbox.ze-dong.cn/dex
5. TLS 握手时，Node.js 使用 NODE_EXTRA_CA_CERTS 中的证书验证服务器证书
6. 验证成功 → 获取 OpenID 配置

## 预期成果
1. API 能够成功获取 Dex 的 OpenID 配置，不再出现证书错误
2. 移除了 `NODE_TLS_REJECT_UNAUTHORIZED: "0"` 不安全配置，恢复正常的证书验证
3. 所有 HTTPS 连接都使用受信任的证书
4. OIDC 认证流程正常工作
5. 证书由 cert-manager 自动管理，包括续签

## 风险评估
- **安全风险**：低 - 使用受信任的证书而不是完全禁用验证
- **兼容性**：需要确认 Node.js 支持 NODE_EXTRA_CA_CERTS 环境变量
- **维护性**：证书自动续签，但 Pod 可能需要重启才能加载新证书
- **回滚方案**：如果出现问题，可以快速恢复到 `NODE_TLS_REJECT_UNAUTHORIZED: "0"` 配置

## 验证方法
1. 检查 Secret 是否包含 ca.crt：`kubectl get secret sandbox.ze-dong.cn-tls -o yaml`
2. 检查 API Pod 环境变量：`kubectl exec -it <api-pod> -- env | grep NODE`
3. 检查证书文件是否挂载：`kubectl exec -it <api-pod> -- ls -la /etc/ssl/certs/dex-ca.crt`
4. 查看 API Pod 日志，确认无证书错误
5. 测试登录流程，验证 OIDC 认证是否正常
6. 使用 curl 在 Pod 内测试 Dex 端点：
   ```bash
   kubectl exec -it <api-pod> -- curl -v https://dex.sandbox.ze-dong.cn/dex/.well-known/openid-configuration
   ```

## 备选方案
如果 cert-manager 证书配置复杂，可以临时恢复使用 `NODE_TLS_REJECT_UNAUTHORIZED: "0"`，但需要明确标注仅用于测试环境。