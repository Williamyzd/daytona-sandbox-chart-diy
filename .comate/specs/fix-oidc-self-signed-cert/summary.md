# 修复 OIDC 自签名证书问题 - 总结报告

## 任务完成状态

### 已完成的任务

#### 任务 1：检查当前证书 Secret 配置 ✅
- ✅ 确认 `sandbox.ze-dong.cn-tls` Secret 存在
- ✅ 验证 Secret 包含必要的 keys：`ca.crt`、`tls.crt`、`tls.key`
- ✅ 检查证书 DNS 名称包含 `sandbox.ze-dong.cn` 和 `*.sandbox.ze-dong.cn`（覆盖 dex.sandbox.ze-dong.cn）

#### 任务 2：修改 values.yaml 配置 API 证书信任 ✅
- ✅ 移除了 `services.api.env` 中的 `NODE_TLS_REJECT_UNAUTHORIZED: "0"`（不安全配置）
- ✅ 添加了 `NODE_EXTRA_CA_CERTS: "/etc/ssl/certs/dex-ca.crt"` 环境变量
- ✅ 配置了 `extraVolumeMounts` 挂载证书到 `/etc/ssl/certs/dex-ca.crt`
- ✅ 配置了 `extraVolumes` 引用 `sandbox.ze-dong.cn-tls` Secret

#### 任务 3：验证 API 部署模板正确应用配置 ✅
- ✅ 确认 `api-deployment.yaml` 模板正确处理 `extraVolumes` 和 `extraVolumeMounts`
- ✅ 确认模板逻辑不会覆盖或忽略 values.yaml 中的配置
- ✅ 在模板中添加了 `NODE_EXTRA_CA_CERTS` 环境变量的条件注入

#### 任务 4：同样修改 Proxy 服务配置（保持一致性）✅
- ✅ 移除了 `services.proxy.env` 中的 `NODE_TLS_REJECT_UNAUTHORIZED: "0"`
- ✅ 添加了 `NODE_EXTRA_CA_CERTS: "/etc/ssl/certs/dex-ca.crt"` 环境变量
- ✅ 配置了 `extraVolumeMounts` 挂载证书
- ✅ 配置了 `extraVolumes` 引用 Secret
- ✅ 在 `proxy-deployment.yaml` 模板中添加了 `NODE_EXTRA_CA_CERTS` 环境变量的条件注入

#### 任务 5：部署更新并验证 ✅（部分完成）
- ✅ 执行 helm upgrade 应用配置更改（成功升级到 revision 3）
- ✅ 等待 API 和 Proxy Pod 重启并就绪
- ✅ 验证 Pod 环境变量包含 `NODE_EXTRA_CA_CERTS`
- ✅ 验证 Pod 中证书文件正确挂载（`/etc/ssl/certs/dex-ca.crt` 存在且可读）
- ✅ 检查 API 日志，启动阶段无证书错误
- 🔄 测试 OIDC 认证流程（待最终验证）

## 技术实现细节

### 1. 修改的文件列表

#### `charts/daytona/values.yaml`
- **API 服务配置**（第 76-83 行）：
  - 移除：`NODE_TLS_REJECT_UNAUTHORIZED: "0"`
  - 添加：`NODE_EXTRA_CA_CERTS: "/etc/ssl/certs/dex-ca.crt"`
  - 配置证书卷挂载和 Secret 引用

- **Proxy 服务配置**（第 310-318 行）：
  - 移除：`NODE_TLS_REJECT_UNAUTHORIZED: "0"`
  - 添加：`NODE_EXTRA_CA_CERTS: "/etc/ssl/certs/dex-ca.crt"`
  - 配置证书卷挂载和 Secret 引用

#### `charts/daytona/templates/api-deployment.yaml`
- **环境变量注入**（第 60-65 行）：
  ```yaml
  # TLS configuration
  {{- if .Values.services.api.env.NODE_EXTRA_CA_CERTS }}
  - name: NODE_EXTRA_CA_CERTS
    value: {{ .Values.services.api.env.NODE_EXTRA_CA_CERTS | quote }}
  {{- end }}
  ```

#### `charts/daytona/templates/proxy-deployment.yaml`
- **环境变量注入**（第 117-122 行）：
  ```yaml
  # TLS configuration
  {{- if .Values.services.proxy.env.NODE_EXTRA_CA_CERTS }}
  - name: NODE_EXTRA_CA_CERTS
    value: {{ .Values.services.proxy.env.NODE_EXTRA_CA_CERTS | quote }}
  {{- end }}
  ```

### 2. 部署验证结果

#### 环境变量验证
```bash
$ kubectl exec daytona-api-xxx -- env | grep NODE
NODE_VERSION=22.22.0
NODE_ENV=production
NODE_EXTRA_CA_CERTS=/etc/ssl/certs/dex-ca.crt
```
✅ `NODE_EXTRA_CA_CERTS` 环境变量正确设置

#### 证书文件挂载验证
```bash
$ kubectl exec daytona-api-xxx -- ls -la /etc/ssl/certs/dex-ca.crt
-rw-r--r--    1 root     2000          1139 Mar 12 16:37 /etc/ssl/certs/dex-ca.crt
```
✅ 证书文件正确挂载且可读

#### 证书有效性验证
```bash
$ kubectl exec daytona-api-xxx -- curl -s --cacert /etc/ssl/certs/dex-ca.crt \
  https://dex.sandbox.ze-dong.cn/dex/.well-known/openid-configuration
```
✅ 使用指定 CA 证书可成功获取 OpenID 配置

#### API 日志验证
```bash
$ kubectl logs daytona-api-xxx --tail=50 | grep -i "certificate\|error\|oidc"
```
✅ 启动阶段无证书相关错误

### 3. 安全改进

**之前**：
- 使用 `NODE_TLS_REJECT_UNAUTHORIZED: "0"` 全局禁用所有 TLS 证书验证
- 所有 HTTPS 连接都不验证服务器证书，存在严重安全隐患

**之后**：
- 使用 `NODE_EXTRA_CA_CERTS` 指定受信任的 CA 证书
- 只有由该 CA 签发的证书会被信任（sandbox.ze-dong.cn 和 *.sandbox.ze-dong.cn）
- 显著提升安全性，同时保持自签名证书环境的兼容性

## 当前状态

### 已解决的问题
1. ✅ 移除了不安全的全局禁用证书验证配置
2. ✅ 配置了 API 和 Proxy 服务信任 cert-manager 管理的自签名 CA 证书
3. ✅ 部署成功，Pod 重启并正确加载配置
4. ✅ 证书文件正确挂载到容器内
5. ✅ 环境变量正确注入

### 待最终验证
1. 🔄 实际的 OIDC 登录流程测试
   - 需要通过浏览器访问 https://sandbox.ze-dong.cn/dashboard
   - 尝试使用 Dex 进行登录
   - 验证不再出现 "Failed to fetch OpenID configuration: self-signed certificate" 错误

2. 🔄 长期运行监控
   - 观察 API 日志，确认持续无证书错误
   - 验证证书续签后的兼容性（90 天后）

## 技术原理说明

### NODE_EXTRA_CA_CERTS 环境变量
- **作用**：指定 Node.js TLS/SSL 连接时额外信任的 CA 证书文件路径
- **机制**：Node.js 在启动时会读取此环境变量，将指定的证书添加到信任存储
- **影响范围**：影响所有使用 Node.js 内置 `https` 模块的请求
- **兼容性**：需要 Node.js 4.0.0+ 版本

### 证书挂载机制
- **Secret 挂载**：通过 Kubernetes Secret 机制将证书挂载到 Pod 文件系统
- **subPath 使用**：只挂载 Secret 中的特定 key（ca.crt）到指定路径
- **权限控制**：证书文件设置为只读，防止意外修改

### 自签名证书信任链
```
自签名 CA (selfsigned-issuer)
    ↓ 签发
服务器证书 (sandbox.ze-dong.cn-tls)
    ↓ 使用
Dex Ingress (dex.sandbox.ze-dong.cn)
    ↓ 访问
API 服务 (信任自签名 CA)
```

## 潜在问题和建议

### 1. 证书续签后的处理
**问题**：cert-manager 会在证书到期前自动续签，新证书的 CA 可能会变化
**建议**：
- 考虑使用 ClusterIssuer 代替 Namespace Issuer，确保证书一致性
- 证书续签后可能需要重启 Pod 以加载新的 CA 证书
- 可以配置 cert-manager 的 cert-manager.io/cluster-issuer 注解

### 2. 多服务证书管理
**当前状态**：API、Proxy、Dex 都使用同一个 TLS Secret
**建议**：
- 如果未来需要不同的证书策略，可以拆分为多个 Secret
- 使用 cert-manager 的 Certificate 资源自动管理多个证书

### 3. 监控和告警
**建议**：
- 添加证书过期监控告警
- 监控 API 日志中的证书相关错误
- 配置证书续签失败告警

## 测试方法

### 手动测试步骤

1. **验证证书挂载**
   ```bash
   kubectl exec -n default <api-pod> -- ls -la /etc/ssl/certs/dex-ca.crt
   ```

2. **验证环境变量**
   ```bash
   kubectl exec -n default <api-pod> -- env | grep NODE_EXTRA_CA_CERTS
   ```

3. **测试 OIDC 配置获取**（从 Pod 内部）
   ```bash
   kubectl exec -n default <api-pod> -- curl -s --cacert /etc/ssl/certs/dex-ca.crt \
     https://dex.sandbox.ze-dong.cn/dex/.well-known/openid-configuration
   ```

4. **测试登录流程**（浏览器）
   - 访问 https://sandbox.ze-dong.cn/dashboard
   - 点击登录
   - 使用 Dex 认证（username: admin, password: password）
   - 验证成功登录且无证书错误

5. **检查 API 日志**
   ```bash
   kubectl logs -n default <api-pod> -f | grep -i "oidc\|certificate"
   ```

## 结论

本次修改成功地将 Daytona API 和 Proxy 服务从不安全的全局禁用证书验证配置，升级为使用受信任的 CA 证书配置。通过 cert-manager 管理的自签名证书现在被正确地挂载到服务容器中，并通过 `NODE_EXTRA_CA_CERTS` 环境变量被 Node.js 应用信任。

主要改进：
- ✅ 安全性显著提升（从完全禁用验证到只信任指定 CA）
- ✅ 配置通过 Helm values.yaml 管理，易于维护
- ✅ 证书由 cert-manager 自动管理，包含续签机制
- ✅ 修改最小化，不影响其他功能

待完成：
- 通过浏览器测试完整的 OIDC 登录流程
- 长期监控证书续签和运行状态

## 附录：相关文件路径

- `charts/daytona/values.yaml` - Helm 配置文件
- `charts/daytona/templates/api-deployment.yaml` - API 部署模板
- `charts/daytona/templates/proxy-deployment.yaml` - Proxy 部署模板
- `charts/cert.yaml` - cert-manager Issuer 和 Certificate 配置
- `charts/daytona/templates/_helpers.tpl` - Helm 模板辅助函数