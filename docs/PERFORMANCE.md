# Campus capacity planning

The intended workload is a college campus with up to approximately 10,000 print
requests per day, including peak periods. Daily print jobs, arriving visitors,
HTTP requests and simultaneous users are different measurements. Plan around
observed peak arrivals, pages per job and queue waiting time.

## Application capacity

The initial topology is one host, one asynchronous application worker and one
PostgreSQL server. No second database or microservices are needed for this design.
Local pre-release simulations maintained 10,000 visitor arrivals/hour for two
minutes and 30,000/hour for five minutes without unexpected HTTP responses. A
heavier two-minute phase at 30,000/hour included 1,000 logins and 1,000 synthetic
20-page PDF upload/cancellation journeys: overall p95 was about 68 ms and upload
p95 about 111 ms. These were short local runs, not a production capacity guarantee.
The development drivers and generated results were removed before publication.

A separate 200-request/second burst exceeded the one-second latency target. Avoid
claiming unrestricted burst capacity. Monitor the deployed workload and tune only
when measurements show a bottleneck. Password hashing and PDF parsing use CPU and
memory; complex PDFs and slow Internet uploads differ from synthetic files.

## Existing bounds

- Uvicorn admits up to 200 concurrent connections/tasks, with overload returning 503.
- SQLAlchemy uses ten pooled connections plus ten overflow connections; one connection holds the singleton lock.
- Database statements have a 15-second deadline; pool checkout has a ten-second deadline.
- Lists have bounded pagination and user identity lookups have case-insensitive indexes.
- PDFs default to 20 MiB and 1,000 pages; the HTTPS proxy limits multipart bodies to 22 MB.
- Uploads check free storage against a configurable reserve before writing.
- The queue cache is bounded; larger queues use database queries.

Keep the database connection budget above the application pool plus maintenance
connections. Do not increase `--workers` or add replicas: printer dispatcher state
and rate-limit counters are process-local, and startup deliberately rejects a
second worker against the same database.

## Printer and storage capacity

At 20 pages/minute, one printer can produce roughly 1,200 pages/hour before other
overheads. Ten thousand jobs per day can require multiple printers or long queues,
depending on pages per job and operating hours. Website capacity cannot increase
physical printer throughput. Agree on acceptable queue age and pickup handling.

Ten thousand 1 MiB uploads produce about 10 GiB of incoming documents; at 20 MiB
each, that approaches 200 GiB. Actual retained storage depends on delivery and
cleanup. Documents are deleted after delivery; monitor disk growth and back up
retained documents with the database. There is no hard global queue admission
quota or automatic retention scheduler.

## Operating and growing

Monitor request p95/p99 latency, errors, 429/503 responses, CPU, memory, disk space,
database connections and oldest queued order. Exercise migration, upload, payment,
printing and recovery behavior on staging before releasing changes. Keep provider
load simulations away from live money.

First tune measured database queries, polling and file limits, then increase host
resources if needed. Multiple workers require durable printer coordination and
shared rate limits first; those can use the existing PostgreSQL database.
