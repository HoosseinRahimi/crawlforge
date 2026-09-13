from prometheus_client import Counter, Gauge, Histogram

requests_total = Counter("crawlforge_requests_total", "HTTP requests", ["method", "path", "status"])
scrapes_total = Counter("crawlforge_scrapes_total", "Scrape attempts", ["method"])
scrape_failures_total = Counter("crawlforge_scrape_failures_total", "Scrape failures", ["code"])
http_scrapes_total = Counter("crawlforge_http_scrapes_total", "HTTP scrapes")
browser_scrapes_total = Counter("crawlforge_browser_scrapes_total", "Browser scrapes")
scrape_duration_seconds = Histogram("crawlforge_scrape_duration_seconds", "Scrape duration")
jobs_queued = Gauge("crawlforge_jobs_queued", "Queued jobs")
browser_contexts_active = Gauge("crawlforge_browser_contexts_active", "Active browser contexts")
proxy_failures_total = Counter("crawlforge_proxy_failures_total", "Proxy failures", ["proxy_id"])
