"""Our own star system and planet for the Commonwealth (docs/planet/planet-probe.md).

esm.py      raw Starfield plugin records: read, edit and write without a schema
records.py  the planet master (star, locations, planet) and the registration override, cloned from the user's own
            Starfield.esm at stage time; the census of the vanilla records they come from
biom.py     the planet's biome map: copied out of the user's own "Starfield - PlanetData.ba2" at stage time
probe_log.py  the planet probe's user log, read into one verdict per arrival
"""
