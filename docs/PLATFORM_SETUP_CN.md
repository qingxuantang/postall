# 平台 API 设置指南

**[English](./PLATFORM_SETUP.md) | [中文](#平台-api-设置指南)**

本指南详细介绍如何获取各个平台的 API 凭证及其频率限制。

---

## 目录

- [Twitter/X](#twitterx)
- [LinkedIn](#linkedin)
- [Instagram](#instagram)
- [Pinterest](#pinterest)
- [Threads](#threads)
- [频率限制汇总](#频率限制汇总)

---

## Twitter/X

### 获取 API 访问权限

1. **创建开发者账号**
   - 访问 [developer.twitter.com](https://developer.twitter.com/)
   - 使用你的 Twitter 账号登录
   - 申请开发者访问权限（有免费层级）

2. **创建项目和应用**
   - 进入 Developer Portal → Projects & Apps
   - 点击 "Create Project"
   - 命名项目并选择用途
   - 在项目中创建一个 App

3. **获取 API 密钥**
   - 在 App 设置中，进入 "Keys and Tokens"
   - 生成以下凭证：
     - **API Key**（Consumer Key）
     - **API Secret**（Consumer Secret）
     - **Bearer Token**
     - **Access Token**
     - **Access Token Secret**

4. **设置应用权限**
   - 进入 App Settings → User authentication settings
   - 启用 OAuth 1.0a
   - 设置权限为 **Read and Write**
   - 添加回调 URL（可以用 `https://localhost`）

### 环境变量

```bash
TWITTER_ENABLED=true
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_SECRET=your_access_secret
```

### 频率限制

| 层级 | 推文/月 | 推文/天 | 推文/15分钟 |
|------|---------|---------|-------------|
| 免费 | 1,500 | ~50 | 50 |
| Basic ($100/月) | 3,000 | ~100 | 100 |
| Pro ($5,000/月) | 300,000 | 10,000 | 300 |

**建议：**
- 免费层级：每天 1-2 条推文
- Basic 层级：每天 3-5 条推文
- 两条推文之间至少等待 1 分钟，避免被检测为垃圾信息

---

## LinkedIn

### 获取 API 访问权限

1. **创建 LinkedIn 公司页面**（如果以公司身份发帖）
   - 访问 [linkedin.com/company/setup](https://www.linkedin.com/company/setup/)
   - 创建你的公司页面

2. **创建 LinkedIn 应用**
   - 访问 [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
   - 点击 "Create App"
   - 填写应用详情：
     - 应用名称
     - LinkedIn 页面（关联到你的页面）
     - 应用 Logo
     - 法律协议

3. **申请 API 产品**
   - 在你的应用中，进入 "Products" 标签
   - 申请访问：
     - **Share on LinkedIn**（发帖必需）
     - **Sign In with LinkedIn using OpenID Connect**

4. **获取凭证**
   - 进入 "Auth" 标签
   - 记录你的 **Client ID** 和 **Client Secret**
   - 添加 OAuth 2.0 重定向 URL：`https://localhost/callback`

5. **获取 Access Token**
   - 使用 OAuth 2.0 流程获取 access token
   - 所需权限范围：`w_member_social`（个人）或 `w_organization_social`（公司）
   
   ```bash
   # 授权 URL
   https://www.linkedin.com/oauth/v2/authorization?
     response_type=code&
     client_id=YOUR_CLIENT_ID&
     redirect_uri=https://localhost/callback&
     scope=openid%20profile%20w_member_social
   ```

6. **获取 Person URN**
   - 认证后，调用：`GET https://api.linkedin.com/v2/userinfo`
   - 你的 URN 是：`urn:li:person:{响应中的 id}`

### 环境变量

```bash
LINKEDIN_ENABLED=true
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
LINKEDIN_ACCESS_TOKEN=your_access_token
LINKEDIN_REFRESH_TOKEN=your_refresh_token
LINKEDIN_PERSON_URN=urn:li:person:xxx
```

### 频率限制

| 操作 | 限制 | 周期 |
|------|------|------|
| 分享/发帖 | 150 | 每天 |
| API 调用 | 100 | 每天每用户 |
| 图片上传 | 1000 | 每天 |

**建议：**
- 每天 1-2 篇帖子以获得最佳互动
- 在工作时间发布（上午 7-9 点，中午 12 点，下午 5-6 点）
- Access token 60 天过期；refresh token 365 天过期

---

## Instagram

### 获取 API 访问权限

Instagram 需要 **Meta Business 账号**，设置相对复杂。

1. **前提条件**
   - Facebook 页面（必需）
   - Instagram 商业或创作者账号
   - Instagram 账号已链接到 Facebook 页面

2. **转换为商业账号**
   - Instagram App → 设置 → 账号 → 切换到专业账号
   - 选择商业或创作者
   - 链接到你的 Facebook 页面

3. **创建 Meta 应用**
   - 访问 [developers.facebook.com](https://developers.facebook.com/)
   - 创建新应用 → 选择 "Business" 类型
   - 添加 "Instagram Graph API" 产品

4. **获取 Access Token**
   - 在 App Dashboard → Instagram Graph API → Generate Token
   - 选择你的 Instagram 账号
   - 授予权限：`instagram_basic`、`instagram_content_publish`

5. **获取 Instagram Business Account ID**
   - 使用 Graph API Explorer
   - 查询：`GET /me/accounts` 获取 Facebook Page ID
   - 查询：`GET /{page-id}?fields=instagram_business_account` 获取 Instagram ID

### 环境变量

```bash
INSTAGRAM_ENABLED=true
INSTAGRAM_ACCESS_TOKEN=your_access_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_ig_business_id
META_APP_SECRET=your_app_secret
```

### 频率限制

| 操作 | 限制 | 周期 |
|------|------|------|
| 内容发布 | 25 | 每 24 小时 |
| API 调用 | 200 | 每小时每用户 |
| 轮播帖子 | 25 | 每 24 小时 |
| Stories | 25 | 每 24 小时 |

**建议：**
- 每天最多 1-3 篇帖子
- 帖子间隔至少 2 小时
- 最佳发布时间：上午 11 点 - 下午 1 点，晚上 7 点 - 9 点

---

## Pinterest

### 获取 API 访问权限

1. **创建商业账号**
   - 访问 [pinterest.com/business/create](https://www.pinterest.com/business/create/)
   - 或将现有账号转换为商业账号

2. **创建 Pinterest 应用**
   - 访问 [developers.pinterest.com](https://developers.pinterest.com/)
   - 点击 "My Apps" → "Create App"
   - 填写应用详情

3. **获取 API 访问权限**
   - 在你的应用中，申请 **Pins API** 访问权限
   - 注意：Pinterest 对生产环境访问有审核流程

4. **获取 Access Token**
   - 使用 OAuth 2.0 流程
   - 所需权限范围：`boards:read`、`pins:read`、`pins:write`
   
   ```bash
   # 授权 URL
   https://api.pinterest.com/oauth/?
     response_type=code&
     client_id=YOUR_APP_ID&
     redirect_uri=YOUR_REDIRECT_URI&
     scope=boards:read,pins:read,pins:write
   ```

### 环境变量

```bash
PINTEREST_ENABLED=true
PINTEREST_ACCESS_TOKEN=your_access_token
PINTEREST_REFRESH_TOKEN=your_refresh_token
PINTEREST_APP_SECRET=your_app_secret
```

### 频率限制

| 操作 | 限制 | 周期 |
|------|------|------|
| 写入操作 | 1,000 | 每天 |
| Pin 创建 | 1,000 | 每天 |
| API 调用（总计） | 1,000 | 每分钟 |
| Board 创建 | 200 | 每天 |

**建议：**
- 每天 5-15 个 pin 以获得最佳增长
- 全天分散发布
- 最佳时间：晚上 8-11 点，尤其是周六

---

## Threads

### 获取 API 访问权限

Threads 使用 Meta API 基础设施（与 Instagram 类似）。

1. **前提条件**
   - 已链接 Threads 的 Instagram 账号
   - Meta 开发者账号

2. **创建 Meta 应用**
   - 访问 [developers.facebook.com](https://developers.facebook.com/)
   - 创建新应用
   - 添加 "Threads API" 产品（如果可用）

3. **获取 Access Token**
   - 使用 Meta OAuth 流程
   - 权限范围：`threads_basic`、`threads_content_publish`

4. **可用性说明**
   - Threads API 相对较新
   - 初期可能访问受限
   - 请查看 Meta 开发者文档获取最新信息

### 环境变量

```bash
THREADS_ENABLED=true
THREADS_ACCESS_TOKEN=your_access_token
```

### 频率限制

| 操作 | 限制 | 周期 |
|------|------|------|
| 帖子 | 250 | 每 24 小时 |
| 回复 | 1,000 | 每 24 小时 |
| API 调用 | 200 | 每小时 |

**建议：**
- 每天 2-5 条 threads
- 参与回复互动以提高曝光
- 最佳时间：与 Instagram 类似

---

## 频率限制汇总

| 平台 | 每日发帖限制 | 建议数量 | 最佳时间 |
|------|--------------|----------|----------|
| Twitter/X（免费） | ~50 | 1-2 | 8 AM, 12 PM, 5 PM |
| Twitter/X（Basic） | ~100 | 3-5 | 8 AM, 12 PM, 5 PM |
| LinkedIn | 150 | 1-2 | 7-9 AM, 12 PM, 5-6 PM |
| Instagram | 25 | 1-3 | 11 AM-1 PM, 7-9 PM |
| Pinterest | 1,000 | 5-15 | 8-11 PM |
| Threads | 250 | 2-5 | 11 AM-1 PM, 7-9 PM |

### 通用最佳实践

1. **不要触及频率限制** - 保持在限制以下，避免账号被标记
2. **分散发帖时间** - 帖子之间至少等待 30-60 分钟
3. **内容多样化** - 不要在各平台发布完全相同的内容
4. **监控互动** - 根据效果调整发帖频率
5. **使用排期功能** - PostAll 会自动处理发布时间

---

## 故障排除

### 常见问题

**"超出频率限制"**
- 等待频率限制窗口重置
- 在配置中降低发帖频率

**"无效的 access token"**
- Token 可能已过期
- 重新认证获取新 token
- LinkedIn token 60 天过期

**"权限被拒绝"**
- 检查应用权限是否匹配所需范围
- 某些平台的特定功能需要应用审核

**"内容未发布"**
- 检查内容是否符合平台准则
- 图片需要满足尺寸/格式要求
- 某些内容可能被平台过滤器标记

---

## 更多资源

- [Twitter API 文档](https://developer.twitter.com/en/docs)
- [LinkedIn API 文档](https://learn.microsoft.com/en-us/linkedin/)
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-api)
- [Pinterest API](https://developers.pinterest.com/docs/api/v5/)
- [Threads API](https://developers.facebook.com/docs/threads)
