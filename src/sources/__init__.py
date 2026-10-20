"""Source registry. Each fetcher returns a list of raw dicts."""
from . import cryptojobslist, himalayas, remoteok, superteam, weworkremotely

REGISTRY = {
    "remoteok": remoteok.fetch,
    "himalayas": himalayas.fetch,
    "weworkremotely": weworkremotely.fetch,
    "cryptojobslist": cryptojobslist.fetch,
    "superteam": superteam.fetch,
}
