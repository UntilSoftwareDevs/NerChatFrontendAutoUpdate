# NerChat!

公开追踪 [Element Web](https://github.com/element-hq/element-web) 的正式 Release，为 `chat.neboer.site` 应用自定义配置，部署到腾讯云 EdgeOne Pages / Makers 免费版中国大陆项目 `nerchat`。

## 自动更新

GitHub Actions 每天北京时间 **03:17** 检查 `/releases/latest`；GitHub 定时任务可能延迟。忽略预发布版。无新版本时不构建、不上传。修改部署代码会重新部署，Actions 页面也可手动运行，勾选 `force` 强制重部署。

流程：获取官方预编译 tarball → 校验 GitHub 提供的 SHA-256 → 安全解压 → 覆盖 `overlay/`（包含隐藏文件）→ 获取并校验 homeserver 的 `/versions` → 校验产物和路由 → 预览部署与 HTTP 验证 → 生产部署与 HTTP 验证 → 提交 `deployed-release.json`。

补丁、下载、校验、预览部署或预览验收失败时不发布生产版本。只有成功发布且验收通过后才更新版本标记；失败会创建或更新同一个 GitHub Issue。生产发布后的 HTTP 验证失败也会报警，此时应检查实际部署并在控制台回滚，版本标记不会前进。流水线串行执行，避免新旧版本相互覆盖。Actions 定时任务在公开仓库长期无活动后可能被 GitHub 停用，需在 Actions 页面重新启用。

## 配置与 Azure 迁移

- `overlay/config.json`：品牌 `NerChat!`，沿用原 homeserver、Jitsi、中文语言、集成和地图配置。MapTiler key 是前端公开配置，建议在 MapTiler 控制台限制允许的来源域名。
- `overlay/.well-known/matrix/client` 和 `server`：原样保留；显式配置 JSON MIME 类型、CORS 和缓存规则。
- `/_matrix/client/versions`：每次部署获取真实 homeserver 响应，失败阻止发布；边缘函数精确路由返回该快照，支持 GET、HEAD、OPTIONS。
- 其余 `/_matrix/client/*` 与 `/_synapse/client/*`：腾讯云原生边缘函数返回 **307**，保留路径和查询参数以及 HTTP 方法，替代旧 JavaScript 跳转页。不转发或代理 Matrix 请求。浏览器跨源跳转仍受目标 homeserver 的 CORS 策略约束。
- `edgeone.json` 替代 `staticwebapp.config.json`。精确 versions 函数优先于通配路由，避免 capability JSON 被误重定向。

## 缓存和安全响应头

遵循 [Element 官方 Web 部署规范](https://web-docs.element.dev/readme-element-web.html)：`/`、`/index.html`、`/config.json`、`/config.*.json`、`/i18n`、`/i18n/*` 和 `/version` 均要求浏览器重新验证，边缘缓存 TTL 为 0；版本标记、manifest、mobile guide、`.well-known` 同样避免陈旧缓存。`/versions` 使用 `no-store`。

带内容哈希的 JS/CSS 等资源保留平台默认长期缓存，不对所有 JavaScript 强行缓存；腾讯云在每次部署后自动失效边缘缓存。现有浏览器已经缓存的旧 Azure 响应不能由新服务器主动清除，切换后首次访问如仍显示旧站可刷新页面。

全站设置官方建议的 `X-Frame-Options: SAMEORIGIN`、`Content-Security-Policy: frame-ancestors 'self'`、`X-Content-Type-Options: nosniff` 和 `X-XSS-Protection: 1; mode=block`。Element 与 homeserver 使用不同域名，并应始终通过 HTTPS 访问。

## 腾讯云项目和域名

- 账号内资源名：`nerchat`（站内品牌为 `NerChat!`）
- Project ID：`makers-kjd68tcyocsk`
- 区域：`mainland`（由 SDK 显式创建，CLI 的区域默认日志不会改变现有项目区域）
- [腾讯云项目控制台](https://console.cloud.tencent.com/edgeone/pages/project/makers-kjd68tcyocsk)
- 自定义域名：`chat.neboer.site`。大陆节点，域名归属已验证；CNAME 目标为 `chat.neboer.site.pages.dnsoe4.com`。
- HTTPS 使用上传的通配符证书 `neboer.site-26.09`（腾讯云证书 ID `byfH3TDS`），覆盖 `neboer.site` 和 `*.neboer.site`，有效期至北京时间 2026-12-09 05:38:48。证书及私钥不存入仓库；按要求不配置证书自动续期。
- 平台默认域名用于临时验收，可能有访问验证和有效期限制，正式入口使用自定义域名。

`EDGEONE_API_TOKEN` 已作为 GitHub Actions Secret 配置，不能提交到仓库。它由腾讯云 CLI 登录生成，具有账号级部署权限；定期在控制台审查并轮换。CI 固定 EdgeOne CLI 版本并提交 npm lockfile，GitHub Actions 固定到提交 SHA。

## 本地操作

需要 Python 3.10+、Node.js 22、已登录的 `gh` 和腾讯云 CLI：

```sh
npm ci --ignore-scripts
python3 scripts/prepare.py
python3 scripts/verify.py
node --test tests/routing.test.mjs
npx edgeone validate
npx edgeone makers deploy ./dist --name nerchat --env preview --site china --skip-ai-gateway-sync --json
```

本地产物位于 `dist/`，下载缓存及部署日志位于 `.work/`，均不提交。`scripts/verify.py <部署URL>` 可验收实际 HTTP 缓存、安全头、JSON、CORS、307 和查询参数。首次创建项目需先完成一次生产部署，腾讯云才允许预览部署。回滚可在腾讯云控制台选择历史生产部署；回滚后检查是否需要暂时停用自动更新。

参考：[Element 安装](https://web-docs.element.dev/install.html)、[腾讯云 CLI](https://edgeone.cloud.tencent.com/pages/document/162936923278893056)、[edgeone.json](https://pages.edgeone.ai/document/edgeone-json)、[腾讯云缓存机制](https://edgeone.ai/document/180002216676458496)。

## MatrixRTC

`overlay/.well-known/matrix/client` advertises the NerChat LiveKit authorization
service. The bundled Element Call handles room calls; legacy 1:1 calling remains
available (`use_exclusively: false`). No anonymous guest SPA link is advertised.
`meet.neboer.site` is a separate frontend, not a Jitsi server.
