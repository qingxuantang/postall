# Networking — Calling APIs from Restricted Regions

Some APIs that PostAll talks to (Gemini, LinkedIn, etc.) refuse requests from certain regions. If you self-host PostAll in one of those regions, you'll see errors like:

```
400 FAILED_PRECONDITION. User location is not supported for the API use.
```

This guide explains why this happens and gives you three concrete ways to work around it without changing PostAll's source code.

> **PostAll already supports proxies natively.** All of PostAll's outbound HTTP traffic goes through Python's standard HTTP clients (`requests`, `httpx`, `google-generativeai`, the LinkedIn / OpenAI / Anthropic SDKs). Every one of them honors the standard `HTTPS_PROXY` and `HTTP_PROXY` environment variables. You do not need to patch any executor code.

---

## TL;DR

Pick one of these three options based on where you run PostAll:

| Option | When to use | Setup time |
|---|---|---|
| **A. HTTPS_PROXY env var** | You already have any proxy (SOCKS, HTTP, residential). Cross-platform. **Recommended.** | 2 minutes |
| **B. Selective routing on Linux** | You self-host on Linux and want only specific APIs to go through a tunnel | 15 minutes |
| **C. Cloudflare WARP** | You want a free, no-config, US/EU exit. Linux/macOS. | 5 minutes |

---

## Known restricted APIs

Today these APIs are known to enforce region checks against the requesting IP. Refusal usually shows up as `400`, `403`, or a redirect to a login page that won't complete.

| API | Service | Symptom |
|---|---|---|
| `generativelanguage.googleapis.com` | Gemini text + image | `User location is not supported` |
| `api.linkedin.com` | LinkedIn publishing | Token gets quietly revoked when authorization and posting IPs disagree |
| `*.openai.com` | OpenAI | `unsupported_country_region_territory` for ~30 country codes |
| `api.anthropic.com` | Anthropic | Region check is permissive but billing has region limits |
| `api.twitter.com` | Twitter / X | Posts may be rate-limited differently per region |

If you self-host PostAll outside the supported regions for any of these, you need one of the workarounds below.

---

## Option A — `HTTPS_PROXY` environment variable

**Recommended.** Works on any OS. No code changes. Routes all PostAll outbound traffic through the proxy you specify.

### Step 1 — get a proxy

Anything that speaks HTTP or SOCKS5 works. Common picks:

- An existing personal SOCKS proxy via SSH:
  ```bash
  ssh -D 1080 -N user@your-overseas-server
  ```
  Now `socks5://127.0.0.1:1080` is your proxy.
- A commercial residential proxy provider.
- A WireGuard / OpenVPN client running in SOCKS proxy mode.

### Step 2 — add to your PostAll `.env`

```bash
# .env (project root or per-project .env)
HTTPS_PROXY=socks5://127.0.0.1:1080
HTTP_PROXY=socks5://127.0.0.1:1080

# Optional — exclude internal hosts from the proxy
NO_PROXY=localhost,127.0.0.1,*.internal
```

If you use Docker, pass these into the container:

```yaml
# docker-compose.yml
services:
  postall-tar:
    environment:
      - HTTPS_PROXY=socks5://host.docker.internal:1080
      - NO_PROXY=localhost,127.0.0.1
```

> Use `host.docker.internal` (not `127.0.0.1`) inside a container so the proxy reference resolves to the host machine.

### Step 3 — verify

```bash
# Should print your proxy's exit IP, not your host's
docker exec postall-tar curl -sS https://ipinfo.io
```

For SOCKS5 specifically: Python's `requests` needs `requests[socks]` extra. PostAll's `requirements.txt` already includes it.

### Pros / cons

- ✅ Works on any OS, including Windows.
- ✅ No code or routing changes.
- ✅ Easy to revert (delete the env var).
- ❌ All PostAll traffic goes through the proxy. If your proxy is slow, image generation gets slower.
- ❌ The proxy operator can see your API destinations and the TLS SNI. They cannot see decrypted payload.

---

## Option B — Selective routing on Linux

**Use when** you self-host on Linux and want fine-grained control. Only specific API endpoints go through the tunnel; everything else uses your normal network path.

### How it works

You run a VPN tunnel (WireGuard, OpenVPN, etc.) but DO NOT set it as the default route. Instead you add `ip route` entries for the specific Google / LinkedIn / OpenAI CIDR ranges so that only those endpoints exit through the tunnel.

### Known CIDR ranges

These are the IP ranges that the most commonly-restricted APIs live in. **Verify before deploying** — IP ranges can change.

```bash
# Google services (includes Gemini)
142.250.0.0/15
172.217.0.0/16
216.58.0.0/16
74.125.0.0/16
173.194.0.0/16
209.85.128.0/17
108.177.0.0/17
64.233.160.0/19
66.102.0.0/20
66.249.80.0/20
72.14.192.0/18
216.239.0.0/16   # generativelanguage.googleapis.com (Gemini)

# LinkedIn API
108.174.0.0/16   # api.linkedin.com
150.171.0.0/16   # linkedin.com
```

### Setup script

Save this as `setup_selective_vpn.sh`:

```bash
#!/bin/bash
# Selective VPN routing — only specific CIDRs go through tun0
# Run after your tunnel comes up

VPN_GATEWAY=10.x.x.1     # your tunnel's gateway IP
VPN_DEV=tun0             # or wg0 for WireGuard
IP=/sbin/ip

# Google CIDRs (Gemini and friends)
$IP route add 142.250.0.0/15 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 172.217.0.0/16 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 216.58.0.0/16  via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 74.125.0.0/16  via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 173.194.0.0/16 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 209.85.128.0/17 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 108.177.0.0/17 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 64.233.160.0/19 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 66.102.0.0/20  via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 66.249.80.0/20 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 72.14.192.0/18 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 216.239.0.0/16 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null

# LinkedIn
$IP route add 108.174.0.0/16 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null
$IP route add 150.171.0.0/16 via $VPN_GATEWAY dev $VPN_DEV 2>/dev/null

# Force IPv4 to avoid IPv6 leaks bypassing the tunnel
echo 1 > /proc/sys/net/ipv6/conf/all/disable_ipv6
echo 1 > /proc/sys/net/ipv6/conf/default/disable_ipv6
```

Make it run at boot via systemd:

```ini
# /etc/systemd/system/postall-selective-vpn.service
[Unit]
Description=PostAll selective VPN routing
After=network-online.target your-vpn.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/path/to/setup_selective_vpn.sh

[Install]
WantedBy=multi-user.target
```

### Verify

```bash
# This should show the route going via the VPN tunnel
ip route get $(dig +short generativelanguage.googleapis.com | head -1)

# This should show your tunnel's exit IP, not your local one
curl -sS https://ipinfo.io
```

### Pros / cons

- ✅ Only restricted APIs go through the tunnel. Latency-sensitive traffic (e.g. domestic LLMs, Anthropic, OpenAI from supported regions) keeps direct routing.
- ✅ No env var changes inside containers — Docker inherits host routing automatically.
- ❌ Linux only. Requires sudo. CIDRs can drift; re-verify periodically.
- ❌ Containers see the same exit IPs as the host. If your tunnel breaks, every container's traffic goes back to the default route silently.

---

## Option C — Cloudflare WARP

**Use when** you want a free, no-config solution and you trust Cloudflare with your TLS SNI.

WARP is Cloudflare's free WireGuard-based VPN. It gives you a US/EU exit, runs anywhere, and is configured in three lines.

### Setup (Linux example)

```bash
curl https://pkg.cloudflareclient.com/install | bash
sudo apt install cloudflare-warp
warp-cli registration new
warp-cli connect
```

After this, your default outbound IP is a WARP IP. PostAll containers inherit this automatically.

### Verify

```bash
curl -sS https://ipinfo.io
# Should show a Cloudflare-owned IP, country US (default)
```

### Pros / cons

- ✅ Free, no signup beyond accepting the WARP terms.
- ✅ One command to enable, one to disable.
- ✅ No CIDR maintenance.
- ❌ ALL outbound traffic from the host goes through Cloudflare. Latency for domestic services may suffer.
- ❌ Some APIs (residential-IP-required services, banking) flat-out refuse Cloudflare-owned IPs.
- ❌ WARP exit pool occasionally gets blocked by services like X / Twitter.

---

## How to know which option to pick

| Your situation | Pick |
|---|---|
| Self-hosting outside US/EU, want to publish content | **A (HTTPS_PROXY)** |
| Self-hosting in mainland China with existing personal proxy | **A (HTTPS_PROXY)** |
| Self-hosting on a Linux VPS with a long-running WireGuard tunnel and need surgical routing | **B (selective routing)** |
| Self-hosting on Linux, no existing VPN, want zero-cost solution | **C (WARP)** |
| Container-only deployment with no host access | **A** (set `HTTPS_PROXY` in docker-compose) |
| Mixed: some APIs from one region, others from another | **B** (route per-CIDR) |

---

## Troubleshooting

### "Why is `HTTPS_PROXY` set but PostAll still hits the original endpoint directly?"

Most common reasons:

1. The env var is not visible inside the container. Verify with:
   ```bash
   docker exec postall-tar env | grep -i proxy
   ```
2. You set `https_proxy` (lowercase) on Windows but the Python lib expects `HTTPS_PROXY` on POSIX. Set both to be safe.
3. The library you're using doesn't honor `HTTPS_PROXY` (rare — `google-generativeai`, `requests`, `httpx`, the LinkedIn SDK all do).

### "WARP works but Gemini still 403s"

Cloudflare's free WARP pool sometimes lands you on an IP Google has blocklisted. Reconnect for a fresh IP:

```bash
warp-cli disconnect && sleep 5 && warp-cli connect
```

### "Selective routing — Gemini works but YouTube transcript fetches fail"

YouTube uses 142.250 and 74.125 CIDRs. Make sure those are in your routing script. They are included in the example above.

### Verifying any setup

```bash
# What CIDR is the API endpoint in?
dig +short generativelanguage.googleapis.com
dig +short api.linkedin.com

# What route will my host take to it?
ip route get $(dig +short generativelanguage.googleapis.com | head -1)

# What's my actual exit IP?
curl -sS https://ipinfo.io
```

---

## What PostAll does NOT do

PostAll deliberately stays out of network-layer configuration. Specifically:

- It does **not** ship with a built-in VPN client.
- It does **not** require a special `bind_interface` option for any executor — Python's stdlib already honors `HTTPS_PROXY`.
- It does **not** modify your routing table at startup.

This is intentional. Network routing is an infrastructure concern that varies per deployment. Coupling PostAll to a specific routing mechanism would make self-hosting harder, not easier. If you have a use case where the env-var approach genuinely doesn't work and you need executor-level networking config, please open an issue.

---

## Related

- [README](../../README.md) — main getting-started guide
- [PLATFORM_SETUP.md](../PLATFORM_SETUP.md) — per-platform OAuth setup
