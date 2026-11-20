# Optional "refresher" service: runs the R pull scripts in pulls/ so the web
# app's "Refresh data" button can update data/seed/. Built only with
#   docker compose --profile refresh up --build
# so the default docker-compose up --build never builds it.
#
# rocker/r2u installs CRAN packages as prebuilt Ubuntu binaries through apt,
# so arrow is never compiled from source. The image is pinned by digest
# because the 24.04 tag moves.
FROM rocker/r2u:24.04@sha256:cf1c8151046db092ec3d4c45bdc67488f0221263f9e857390f367a41b20c953c

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1

# Binary packages from r2u. r-cran-hoopr pulls in hoopR's dependencies as
# binaries too; hoopR itself is replaced below.
RUN apt-get update \
 && apt-get install -y --no-install-recommends r-cran-hoopr r-cran-arrow r-cran-dplyr r-cran-jsonlite \
 && rm -rf /var/lib/apt/lists/*

# r2u has hoopR 3.1.0, which lacks loaders the pulls use (for example
# load_nba_stats_game_matchups). Install hoopR from the SportsDataverse
# r-universe, the same source as the developer's laptop. Its dependencies
# are already installed, so only hoopR itself is added.
RUN Rscript -e 'if (requireNamespace("bspm", quietly = TRUE)) bspm::disable(); install.packages("hoopR", repos = "https://sportsdataverse.r-universe.dev", dependencies = FALSE)'

# Fail the build with a clear message if hoopR is too old or arrow is missing.
# Without arrow, most load_nba_stats_* calls return empty tables.
RUN Rscript -e ' \
  if (!requireNamespace("arrow", quietly = TRUE)) stop("BUILD CHECK FAILED: the arrow package is missing. Without it the pulls return empty tables."); \
  v <- packageVersion("hoopR"); \
  if (v < "3.2.0") stop(sprintf("BUILD CHECK FAILED: hoopR %s is installed but 3.2.0 or newer is required.", v)); \
  for (p in c("hoopR", "arrow", "dplyr", "jsonlite")) cat(sprintf("%s %s\n", p, packageVersion(p))); \
  cat(R.version.string, "\n")'

WORKDIR /work
COPY server.py /srv/server.py
EXPOSE 8080
CMD ["python3", "/srv/server.py"]
