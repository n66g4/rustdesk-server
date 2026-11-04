# rustdesk-server（fnOS）

基于官方 [rustdesk/rustdesk-server](https://github.com/rustdesk/rustdesk-server) **1.1.16**，移植与 lejianwen API 对接的 **JWT / MUST_LOGIN**，并打包为飞牛 fnOS **原生二进制 `.fpk`**（x86_64）。

当前发行包版本：**1.1.16-9**

- 仓库：https://github.com/n66g4/rustdesk-server
- Release：https://github.com/n66g4/rustdesk-server/releases

## 组件

| 组件 | 说明 |
| --- | --- |
| `hbbs` / `hbbr` | 官方 1.1.16 + `--must-login` / `RUSTDESK_API_JWT_KEY` |
| `rustdesk-api` | [lejianwen/rustdesk-api](https://github.com/lejianwen/rustdesk-api) v2.7 Linux amd64 |
| `fpk/` | fnOS 应用包源（`fnpack build`） |

## 安装

1. 在飞牛应用中心导入 `rustdesk-server.fpk`
2. 按安装向导填写域名/IP、端口、Key（可留空）等
3. 点击桌面图标 → **先进入配置面板**（域名/端口/Key）→ 点「管理后台」打开 `http://<NAS>:<API端口>/_admin/`

### 管理后台默认账密

- 用户名：`admin`
- 密码：首次启动**随机生成**，写入套件日志（查找 `Admin Password Is:`）
- 重置：在应用目录执行 `./bin/rustdesk-api reset-admin-pwd <新密码>`

## 配置面板（桌面图标）

对齐群晖 SPK：桌面入口为 CGI iframe（`/cgi/ThirdParty/rustdesk-server/index.cgi/`），可配置：

| 项 | 说明 |
| --- | --- |
| 域名 / IP | 客户端访问用主机名，不要带端口；留空为 `127.0.0.1` |
| API 协议 / 端口 | `http` 或 `https`，默认端口 `21114` |
| ID 端口 (hbbs) | 默认 `21116`（另需开放端口-1 NAT、端口+2 WebSocket） |
| 中继端口 (hbbr) | 默认 `21117`（另需开放端口+2 WebSocket） |
| Key（公钥） | 留空则使用已生成公钥；也可粘贴已有公钥 |
| MUST_LOGIN | 强制客户端先登录 API |

保存后写入 `etc/wizard.conf` 并同步 `config.yaml`。重载对齐群晖：包内监督进程托管 hbbs/hbbr/api；面板 `kill` API（或仅写配置）触发整组重拉。

升级后请先在应用中心 **停止 → 启动** 一次以加载新监督进程。
## 强制登录（可选）

1. API 与 `hbbs` 共用 JWT：`config.yaml` 的 `jwt.key` → 环境变量 `RUSTDESK_API_JWT_KEY`
2. 在应用设置开启「强制登录」，或设 `MUST_LOGIN=Y`
3. 密钥为空时开启强制登录会拒绝打洞（不会放行任意 token）

默认 `MUST_LOGIN=N`。

## 默认端口

| 服务 | 端口 |
| --- | --- |
| API / 管理后台 | `21114` |
| ID（hbbs）TCP/UDP | `21116` |
| 中继（hbbr） | `21117` |

## 本地构建 FPK

```bash
# Linux x86_64 静态二进制（推荐用 CI；本机可用 musl / cargo-zigbuild）
cargo build --release --target x86_64-unknown-linux-musl --bin hbbs --bin hbbr

# 组装并打包（需 fnpack、gh，会拉取 rustdesk-api 发行包）
bash scripts/assemble-fpk.sh
```

产物在 `dist/rustdesk-server.fpk`。

GitHub Actions 工作流 `Build fnOS FPK`：`workflow_dispatch` 或推送 `v*` tag。

## 目录说明

```
fpk/                 # fnOS 包源
  wizard/            # install / config / uninstall 向导
  cmd/               # 生命周期脚本（main、*_callback、_common）
  app/conf/          # 默认 config.yaml
  app/ui/            # 桌面入口：index.cgi + api.cgi + www 配置面板
scripts/assemble-fpk.sh
src/jwt.rs           # JWT 校验
```

## 许可证

- `hbbs` / `hbbr`：上游 AGPL
- `rustdesk-api`：遵循 [lejianwen/rustdesk-api](https://github.com/lejianwen/rustdesk-api) 许可
