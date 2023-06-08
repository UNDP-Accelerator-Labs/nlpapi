-- location cache
CREATE TABLE IF NOT EXISTS public.location_cache
(
    query TEXT COLLATE pg_catalog."default" UNIQUE NOT NULL PRIMARY KEY,
    id SERIAL UNIQUE NOT NULL,
    access_last TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    access_count INTEGER NOT NULL DEFAULT 1,
    no_cache BOOLEAN NOT NULL,
);
CREATE TABLE IF NOT EXISTS public.location_entries
(
    location_id INTEGER NOT NULL REFERENCES public.location_cache(id) ON UPDATE CASCADE ON DELETE CASCADE,
    pos INTEGER NOT NULL,
    lat DOUBLE PRECISION NOT NULL,
    lng DOUBLE PRECISION NOT NULL,
    formatted TEXT COLLATE pg_catalog."default" NOT NULL,
    country VARCHAR(5) COLLATE pg_catalog."default" NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    CONSTRAINT location_entries_pkey PRIMARY KEY (location_id, pos)
);
