# rustdesk-server（fnOS）

基于官方 [rustdesk/rustdesk-server](https://github.com/rustdesk/rustdesk-server) **1.1.16**，移植了与 lejianwen API 对接的 **JWT / MUST_LOGIN** 能力，并打包为飞牛 fnOS **原生二进制 `.fpk`**。

## 组件

| 组件 | 说明 |
| --- | --- |
| `hbbs` / `hbbr` | 官方 1.1.16 + `--must-login` / `RUSTDESK_API_JWT_KEY` |
| `rustdesk-api` | [lejianwen/rustdesk-api](https://github.com/lejianwen/rustdesk-api) Linux amd64 发行包 |
| `fpk/` | fnOS 应用包源（`fnpack build`） |

## 强制登录（可选）

1. API 与 `hbbs` 共用 JWT 密钥：`config.yaml` 的 `jwt.key`，启动时导出为 `RUSTDESK_API_JWT_KEY`
2. 设置环境变量 `MUST_LOGIN=Y`（或 `hbbs --must-login=Y`）后，打洞前必须携带有效登录 token

默认 `MUST_LOGIN=N`，便于首次安装。

## 默认端口

- API / 管理后台：`21114`
- ID 服务器（hbbs）：`21116`（TCP/UDP）
- 中继（hbbr）：`21117`

## 本地构建 FPK（Linux x86_64 产物）

```bash
# 交叉编译（推荐 CI；本机需 musl 或 cargo-zigbuild）
cargo build --release --target x86_64-unknown-linux-musl --bin hbbs --bin hbbr

# 组装并打包（需 fnpack、gh）
bash scripts/assemble-fpk.sh
```

GitHub Actions：`Build fnOS FPK`（`workflow_dispatch` 或打 `v*` tag）。

## 许可证

服务端代码遵循上游 AGPL；API 二进制来自 lejianwen/rustdesk-api 各自许可。
