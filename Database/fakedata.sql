WITH a AS (
    SELECT random() AS r_lvl, random() AS r_ts, random() AS r_app,
           random() AS r_msg, random() AS r_rt,  random() AS r_code
    FROM generate_series(1, 5000)
),
b AS (
    SELECT *,
           CASE WHEN r_lvl < 0.70 THEN 'INFO'
                WHEN r_lvl < 0.90 THEN 'WARNING'
                ELSE 'ERROR' END AS lvl
    FROM a
),
c AS (
    SELECT *,
           CASE lvl WHEN 'INFO'    THEN 10   + floor(r_rt * 790)::int
                    WHEN 'WARNING' THEN 800  + floor(r_rt * 2200)::int
                    ELSE                 1000 + floor(r_rt * 4000)::int END AS rt,
           CASE lvl WHEN 'INFO'    THEN (ARRAY[200, 201])[1 + floor(r_code * 2)::int]
                    WHEN 'WARNING' THEN (ARRAY[400, 404, 429])[1 + floor(r_code * 3)::int]
                    ELSE                 (ARRAY[500, 503])[1 + floor(r_code * 2)::int] END AS code
    FROM b
)
INSERT INTO logs (event_id, timestamp, application, level, message,
                  response_time, status_code, is_anomaly)
SELECT gen_random_uuid(),
       now() - r_ts * interval '24 hours',
       (ARRAY['Banking', 'Ecommerce', 'CloudStorage'])[1 + floor(r_app * 3)::int],
       lvl,
       CASE lvl
         WHEN 'INFO'    THEN (ARRAY['Request processed successfully', 'User authentication successful'])[1 + floor(r_msg * 2)::int]
         WHEN 'WARNING' THEN (ARRAY['Server response delayed', 'Slow database query'])[1 + floor(r_msg * 2)::int]
         ELSE                (ARRAY['Database connection failed', 'Payment processing error'])[1 + floor(r_msg * 2)::int]
       END,
       rt,
       code,
       (rt > 2000 OR code >= 500 OR lvl = 'ERROR')
FROM c;