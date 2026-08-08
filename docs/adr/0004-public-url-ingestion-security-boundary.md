# ADR 0004: Treat public-URL ingestion as an SSRF-sensitive boundary

- Status: Accepted
- Date: 2026-08-09

## Context

VerityGraph lets a user ask the backend to retrieve a public URL. That capability can become a server-side request forgery (SSRF) primitive if user input is passed directly to an HTTP client. A malicious URL could target loopback interfaces, cloud metadata services, private networks, link-local addresses, internal admin services, or a safe public host that redirects to one of those targets.

The product also needs a stable extraction pipeline without outsourcing retrieval to a third-party or paid API.

## Decision

Public web ingestion is split into two trust stages:

```text
user URL
   |
   v
SafeHttpWebFetcher
   |  scheme / credentials / port
   |  DNS + IP classification
   |  redirect revalidation
   |  timeout / MIME / size limits
   v
bounded approved bytes
   |
   v
Trafilatura main-content extraction
   |
   v
SourceDocument + SourceSpan[]
```

Trafilatura is used only for content extraction from bytes that VerityGraph already retrieved through its security boundary. It is not allowed to perform the network fetch itself.

## Application-level controls

The live fetcher:

1. accepts only HTTP and HTTPS;
2. rejects embedded URL credentials;
3. requires the standard scheme port (80 for HTTP, 443 for HTTPS);
4. resolves hostnames before each request;
5. rejects the target if any resolved address is private, loopback, link-local, multicast, reserved, unspecified, or otherwise non-global;
6. applies the same validation to every redirect target;
7. disables automatic redirect following and enforces a redirect limit;
8. applies a request timeout;
9. accepts only HTML, XHTML, and plain-text responses;
10. checks declared content length when present;
11. also enforces the body-size limit while streaming, so a missing or false `Content-Length` cannot bypass the limit;
12. does not send user-supplied authorization credentials or cookies;
13. does not implement authentication/paywall/access-control bypasses.

## DNS-rebinding / TOCTOU limitation

Application code validates DNS answers and then the HTTP stack opens a connection. DNS can theoretically change between those steps. This implementation reduces SSRF exposure substantially but does not pretend to replace infrastructure-level egress controls.

Production deployments should additionally restrict the backend container's outbound network access so it cannot route to private/internal ranges or metadata endpoints even if application validation fails or a DNS-rebinding condition occurs.

## Deterministic QA

Browser E2E uses `FixtureWebFetcher`, selected only when:

```text
VERITYGRAPH_WEB_PROVIDER=fixture
```

The fixture replaces only the external network boundary. The real FastAPI route, main-content extraction, canonical source creation, repository persistence, and React provenance preview still run.

Security behavior is covered separately with mocked HTTP transport and resolver tests, including:

- non-HTTP schemes;
- embedded credentials;
- nonstandard ports;
- loopback/private/link-local targets;
- mixed public/private DNS answer sets;
- redirects to private targets;
- unsupported MIME types;
- declared and streamed oversized bodies.

## Consequences

### Positive

- public URL ingestion remains free and local-first;
- the network trust boundary is independently testable;
- external content extractors cannot accidentally bypass URL policy;
- redirects cannot silently pivot to internal services;
- deterministic E2E remains independent of third-party uptime.

### Trade-offs

- sites served on nonstandard ports are intentionally unsupported by default;
- some JavaScript-heavy pages may not expose useful server-rendered content;
- app-level SSRF controls still require infrastructure egress hardening for high-assurance deployments;
- authenticated/private pages are outside the product's public-source scope.
