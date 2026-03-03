# Platform API Setup Guide

**[English](#platform-api-setup-guide) | [中文](./PLATFORM_SETUP_CN.md)**

This guide explains how to obtain API credentials for each supported platform and their rate limits.

---

## Table of Contents

- [Twitter/X](#twitterx)
- [LinkedIn](#linkedin)
- [Instagram](#instagram)
- [Pinterest](#pinterest)
- [Threads](#threads)
- [Rate Limits Summary](#rate-limits-summary)

---

## Twitter/X

### Getting API Access

1. **Create a Developer Account**
   - Go to [developer.twitter.com](https://developer.twitter.com/)
   - Sign in with your Twitter account
   - Apply for developer access (Free tier available)

2. **Create a Project and App**
   - Go to Developer Portal → Projects & Apps
   - Click "Create Project"
   - Name your project and select use case
   - Create an App within the project

3. **Get API Keys**
   - In your App settings, go to "Keys and Tokens"
   - Generate the following:
     - **API Key** (Consumer Key)
     - **API Secret** (Consumer Secret)
     - **Bearer Token**
     - **Access Token**
     - **Access Token Secret**

4. **Set App Permissions**
   - Go to App Settings → User authentication settings
   - Enable OAuth 1.0a
   - Set permissions to **Read and Write**
   - Add callback URL (can be `https://localhost`)

### Environment Variables

```bash
TWITTER_ENABLED=true
TWITTER_API_KEY=your_api_key
TWITTER_API_SECRET=your_api_secret
TWITTER_BEARER_TOKEN=your_bearer_token
TWITTER_ACCESS_TOKEN=your_access_token
TWITTER_ACCESS_SECRET=your_access_secret
```

### Rate Limits

| Tier | Tweets/Month | Tweets/Day | Tweets/15min |
|------|--------------|------------|--------------|
| Free | 1,500 | ~50 | 50 |
| Basic ($100/mo) | 3,000 | ~100 | 100 |
| Pro ($5,000/mo) | 300,000 | 10,000 | 300 |

**Recommendations:**
- Free tier: 1-2 tweets per day
- Basic tier: 3-5 tweets per day
- Wait at least 1 minute between tweets to avoid spam detection

---

## LinkedIn

### Getting API Access

1. **Create a LinkedIn Page** (if posting as a company)
   - Go to [linkedin.com/company/setup](https://www.linkedin.com/company/setup/)
   - Create your company page

2. **Create a LinkedIn App**
   - Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
   - Click "Create App"
   - Fill in app details:
     - App name
     - LinkedIn Page (associate with your page)
     - App logo
     - Legal agreement

3. **Request API Products**
   - In your app, go to "Products" tab
   - Request access to:
     - **Share on LinkedIn** (required for posting)
     - **Sign In with LinkedIn using OpenID Connect**

4. **Get Credentials**
   - Go to "Auth" tab
   - Note your **Client ID** and **Client Secret**
   - Add OAuth 2.0 redirect URL: `https://localhost/callback`

5. **Get Access Token**
   - Use OAuth 2.0 flow to get access token
   - Scopes needed: `w_member_social` (personal) or `w_organization_social` (company)
   
   ```bash
   # Authorization URL
   https://www.linkedin.com/oauth/v2/authorization?
     response_type=code&
     client_id=YOUR_CLIENT_ID&
     redirect_uri=https://localhost/callback&
     scope=openid%20profile%20w_member_social
   ```

6. **Get Person URN**
   - After authentication, call: `GET https://api.linkedin.com/v2/userinfo`
   - Your URN is: `urn:li:person:{id from response}`

### Environment Variables

```bash
LINKEDIN_ENABLED=true
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
LINKEDIN_ACCESS_TOKEN=your_access_token
LINKEDIN_REFRESH_TOKEN=your_refresh_token
LINKEDIN_PERSON_URN=urn:li:person:xxx
```

### Rate Limits

| Action | Limit | Period |
|--------|-------|--------|
| Share/Post | 150 | per day |
| API calls | 100 | per day per user |
| Image upload | 1000 | per day |

**Recommendations:**
- 1-2 posts per day for best engagement
- Post during business hours (7-9 AM, 12 PM, 5-6 PM)
- Access tokens expire in 60 days; refresh tokens in 365 days

---

## Instagram

### Getting API Access

Instagram requires a **Meta Business Account** and is more complex to set up.

1. **Prerequisites**
   - Facebook Page (required)
   - Instagram Business or Creator Account
   - Instagram account linked to Facebook Page

2. **Convert to Business Account**
   - Instagram App → Settings → Account → Switch to Professional Account
   - Choose Business or Creator
   - Link to your Facebook Page

3. **Create Meta App**
   - Go to [developers.facebook.com](https://developers.facebook.com/)
   - Create a new app → Select "Business" type
   - Add "Instagram Graph API" product

4. **Get Access Token**
   - In App Dashboard → Instagram Graph API → Generate Token
   - Select your Instagram account
   - Grant permissions: `instagram_basic`, `instagram_content_publish`

5. **Get Instagram Business Account ID**
   - Use Graph API Explorer
   - Query: `GET /me/accounts` to get Facebook Page ID
   - Query: `GET /{page-id}?fields=instagram_business_account` to get Instagram ID

### Environment Variables

```bash
INSTAGRAM_ENABLED=true
INSTAGRAM_ACCESS_TOKEN=your_access_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_ig_business_id
META_APP_SECRET=your_app_secret
```

### Rate Limits

| Action | Limit | Period |
|--------|-------|--------|
| Content Publishing | 25 | per 24 hours |
| API calls | 200 | per hour per user |
| Carousel posts | 25 | per 24 hours |
| Stories | 25 | per 24 hours |

**Recommendations:**
- 1-3 posts per day maximum
- Space posts at least 2 hours apart
- Best posting times: 11 AM - 1 PM, 7 PM - 9 PM

---

## Pinterest

### Getting API Access

1. **Create Business Account**
   - Go to [pinterest.com/business/create](https://www.pinterest.com/business/create/)
   - Or convert existing account to Business

2. **Create Pinterest App**
   - Go to [developers.pinterest.com](https://developers.pinterest.com/)
   - Click "My Apps" → "Create App"
   - Fill in app details

3. **Get API Access**
   - In your app, request access to the **Pins API**
   - Note: Pinterest has a review process for production access

4. **Get Access Token**
   - Use OAuth 2.0 flow
   - Scopes needed: `boards:read`, `pins:read`, `pins:write`
   
   ```bash
   # Authorization URL
   https://api.pinterest.com/oauth/?
     response_type=code&
     client_id=YOUR_APP_ID&
     redirect_uri=YOUR_REDIRECT_URI&
     scope=boards:read,pins:read,pins:write
   ```

### Environment Variables

```bash
PINTEREST_ENABLED=true
PINTEREST_ACCESS_TOKEN=your_access_token
PINTEREST_REFRESH_TOKEN=your_refresh_token
PINTEREST_APP_SECRET=your_app_secret
```

### Rate Limits

| Action | Limit | Period |
|--------|-------|--------|
| Write operations | 1,000 | per day |
| Pin creation | 1,000 | per day |
| API calls (total) | 1,000 | per minute |
| Board creation | 200 | per day |

**Recommendations:**
- 5-15 pins per day for optimal growth
- Space pins throughout the day
- Best times: 8-11 PM, especially Saturdays

---

## Threads

### Getting API Access

Threads uses the Meta API infrastructure (similar to Instagram).

1. **Prerequisites**
   - Instagram account linked to Threads
   - Meta Developer account

2. **Create Meta App**
   - Go to [developers.facebook.com](https://developers.facebook.com/)
   - Create a new app
   - Add "Threads API" product (if available)

3. **Get Access Token**
   - Use Meta OAuth flow
   - Scopes: `threads_basic`, `threads_content_publish`

4. **Note on Availability**
   - Threads API is relatively new
   - May have limited access initially
   - Check Meta developer documentation for latest info

### Environment Variables

```bash
THREADS_ENABLED=true
THREADS_ACCESS_TOKEN=your_access_token
```

### Rate Limits

| Action | Limit | Period |
|--------|-------|--------|
| Posts | 250 | per 24 hours |
| Replies | 1,000 | per 24 hours |
| API calls | 200 | per hour |

**Recommendations:**
- 2-5 threads per day
- Engage with replies for better reach
- Best times: Similar to Instagram

---

## Rate Limits Summary

| Platform | Daily Post Limit | Recommended | Best Times |
|----------|------------------|-------------|------------|
| Twitter/X (Free) | ~50 | 1-2 | 8 AM, 12 PM, 5 PM |
| Twitter/X (Basic) | ~100 | 3-5 | 8 AM, 12 PM, 5 PM |
| LinkedIn | 150 | 1-2 | 7-9 AM, 12 PM, 5-6 PM |
| Instagram | 25 | 1-3 | 11 AM-1 PM, 7-9 PM |
| Pinterest | 1,000 | 5-15 | 8-11 PM |
| Threads | 250 | 2-5 | 11 AM-1 PM, 7-9 PM |

### General Best Practices

1. **Don't hit rate limits** - Stay well under the limits to avoid account flags
2. **Space out posts** - Wait at least 30-60 minutes between posts
3. **Vary content** - Don't post identical content across platforms
4. **Monitor engagement** - Adjust posting frequency based on results
5. **Use scheduling** - PostAll handles timing automatically

---

## Troubleshooting

### Common Issues

**"Rate limit exceeded"**
- Wait for the rate limit window to reset
- Reduce posting frequency in your config

**"Invalid access token"**
- Tokens may have expired
- Re-authenticate to get new tokens
- LinkedIn tokens expire in 60 days

**"Permission denied"**
- Check app permissions match required scopes
- Some platforms require app review for certain features

**"Content not published"**
- Check content meets platform guidelines
- Images must meet size/format requirements
- Some content may be flagged by platform filters

---

## Additional Resources

- [Twitter API Documentation](https://developer.twitter.com/en/docs)
- [LinkedIn API Documentation](https://learn.microsoft.com/en-us/linkedin/)
- [Instagram Graph API](https://developers.facebook.com/docs/instagram-api)
- [Pinterest API](https://developers.pinterest.com/docs/api/v5/)
- [Threads API](https://developers.facebook.com/docs/threads)
