# 修复 OIDC 自签名证书问题 - 任务计划

- [x] 任务 1：检查当前证书 Secret 配置
    - 1.1: 使用 kubectl 检查 sandbox.ze-dong.cn-tls Secret 是否存在
    - 1.2: 验证 Secret 中包含的 key（tls.crt, tls.key, ca.crt）
    - 1.3: 检查证书的 DNS 名称是否包含 *.sandbox.ze-dong.cn

- [x] 任务 2：修改 values.yaml 配置 API 证书信任
    - 2.1: 移除 services.api.env 中的 NODE_TLS_REJECT_UNAUTHORIZED: "0"
    - 2.2: 添加 NODE_EXTRA_CA_CERTS 环境变量指向证书文件
    - 2.3: 配置 extraVolumeMounts 挂载证书到 /etc/ssl/certs/dex-ca.crt
    - 2.4: 配置 extraVolumes 引用 sandbox.ze-dong.cn-tls Secret

- [x] 任务 3：验证 API 部署模板正确应用配置
    - 3.1: 检查 api-deployment.yaml 模板是否正确处理 extraVolumes 和 extraVolumeMounts
    - 3.2: 确认模板逻辑不会覆盖或忽略 values.yaml 中的配置
    - 3.3: 如有必要，修改模板以确保证书挂载和 环境变量正确注入

- [x] 任务 4：同样修改 Proxy 服务配置（保持一致性）
    - 4.1: 移除 services.proxy.env 中的 NODE_TLS_REJECT_UNAUTHORIZED: "0"
    - 4.2: 添加 NODE_EXTRA_CA_CERTS 环境变量
    - 4.3: 配置 extraVolumeMounts 挂载证书
    - 4.4: 配置 extraVolumes 引用 Secret

- [x] 任务 5：部署更新并验证
    - 5.1: 执行 helm upgrade 应用配置更改
    - 5.2: 等待 API 和 Proxy Pod 重启并就绪
    - 5.3: 验证 Pod 环境变量包含 NODE_EXTRA_CA_CERTS
    - 5.4: 验证 Pod 中证书文件正确挂载
    - 5.5: 检查 API 日志，确认无证书错误
    - 5.6: 测试 OIDC 认证流程，验证登录功能
