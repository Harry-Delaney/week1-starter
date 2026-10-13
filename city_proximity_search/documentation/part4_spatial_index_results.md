# Part 4: Spatial Indexes, Query Optimisation and Testing

## 4.1 Spatial index

`City._meta.db_table` is `cities_api_city` (20 rows). `\d cities_api_city` shows the
GeoDjango default spatial index on the `location` field:

```
"cities_api_city_location_5e706dd4_id" gist (location)
```

The field does not set `spatial_index=False`, and `makemigrations cities_api --check`
reports no changes, so no second GiST index or new migration was added.

## 4.2 Query plan

The ORM generates `ORDER BY ST_DistanceSphere(location, <point>) LIMIT 10`.

Before `.only(...)` (all 12 columns selected):

```
Limit  (cost=762.05..762.07 rows=10 width=1249)
  ->  Sort  Sort Key: st_distance(geography(location), <point>::geography, false)
        ->  Seq Scan on cities_api_city  Filter: (location IS NOT NULL)
```

After `.only("id", "name", "country", "population", "location")`, the plan shape is the
same but the row width drops from 1249 to 688 bytes:

```
Limit  (cost=762.05..762.07 rows=10 width=688) (actual time=0.044..0.045 rows=10 loops=1)
  ->  Sort  (cost=762.05..762.20 rows=60 width=688) (actual time=0.043..0.044 rows=10 loops=1)
        Sort Key: (st_distance(geography(location), '0101...4A40'::geography, false))
        Sort Method: quicksort  Memory: 27kB
        ->  Seq Scan on cities_api_city  (cost=0.00..760.75 rows=60 width=688) (actual time=0.027..0.040 rows=20 loops=1)
              Filter: (location IS NOT NULL)
Planning Time: 0.033 ms
Execution Time: 0.096 ms
```

The `/api/cities/nearest/` and `/api/cities/radius/` responses for Dublin were
byte-for-byte identical before and after the change: the same ten cities in the same
order with the same distances.

## Task 3: Average query time

`docker compose run --rm web python manage.py test_proximity_performance`
(20 timed runs per point after one warm-up run; local Docker on macOS; 20 cities):

| Test point | Average | Min  | Max  |
|------------|---------|------|------|
| Dublin     | 0.45 ms | 0.40 | 0.80 |
| London     | 0.41 ms | 0.38 | 0.53 |
| New York   | 0.41 ms | 0.39 | 0.44 |
| Tokyo      | 0.41 ms | 0.39 | 0.44 |
| Sydney     | 0.41 ms | 0.39 | 0.44 |
| **Overall**| **0.42 ms** |  |      |

The first cold query in a fresh shell took about 44 ms, mostly one-off setup for the
PostGIS geography functions. These figures depend on the dataset size and on the local
Docker environment.

### Does the spatial index appear in the plan?

No. The plan uses a **Seq Scan** followed by a **Sort**, and does not use
`cities_api_city_location_5e706dd4_id`. There are two reasons:

1. **The ordering expression cannot use the index.** Django orders by
   `ST_DistanceSphere(...)`, which PostgreSQL rewrites as `st_distance(geography(location), ...)`.
   A GiST index can only speed up `ORDER BY` through the KNN distance operator `<->`
   on the indexed column. It cannot help with the result of a function call. The radius
   endpoint has the same limitation, because its filter is
   `ST_DistanceSphere(...) <= radius`.
2. **The table is tiny.** With 20 rows on a single page, a sequential scan is cheaper
   than any index lookup, so the planner would choose it even when an index could be used.

To confirm that the index itself works, I ran a KNN query with `enable_seqscan = off`.
The planner then used the index:

```
Limit
  ->  Index Scan using cities_api_city_location_5e706dd4_id on cities_api_city
        Order By: (location <-> '0101...4A40'::geometry)
```

Running the ORM's `ST_DistanceSphere` ordering with `enable_seqscan = off` still gives a
Seq Scan + Sort, which confirms that the query shape, not the index, is the limiting
factor. For a large dataset, the next step would be to fetch candidates with `<->` (or
use `ST_DWithin` on geography) and then compute exact spherical distances. With 20 rows
this would not make any measurable difference.
