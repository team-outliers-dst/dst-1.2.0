CREATE DATABASE bengaluru_mobility;
USE bengaluru_mobility;
show tables;

USE bengaluru_mobility;



SELECT 'traffic_readings' AS table_name,
       COUNT(*) AS total_rows
FROM traffic_readings
UNION ALL
SELECT 'weather_aug_sep_import', COUNT(*)
FROM weather_aug_sep_import
UNION ALL
SELECT 'weather_oct_sep_import', COUNT(*)
FROM weather_oct_sep_import
UNION ALL
SELECT 'metro_station_hourly', COUNT(*)
FROM metro_station_hourly

UNION ALL

SELECT 'metro_daily_ticket', COUNT(*)
FROM metro_daily_ticket
UNION ALL

SELECT 'trends_daily_traffic', COUNT(*)
FROM trends_daily_traffic
UNION ALL
SELECT 'trends_daily_metro', COUNT(*)
FROM trends_daily_metro;

DESCRIBE traffic_readings;


CREATE TABLE weather_hourly (
    route_code VARCHAR(60) NOT NULL,
    route_name VARCHAR(100) NOT NULL,
    weather_location VARCHAR(100) NOT NULL,
    timestamp_ist DATETIME NOT NULL,
    date DATE NOT NULL,
    hour TINYINT UNSIGNED NOT NULL,
    day_of_week VARCHAR(15),
    temperature_2m DECIMAL(5,2),
    apparent_temperature DECIMAL(5,2),
    relative_humidity_2m DECIMAL(5,2),
    precipitation DECIMAL(6,2),
    rain DECIMAL(6,2),
    weather_code SMALLINT UNSIGNED,
    rain_status VARCHAR(20),
    PRIMARY KEY (route_code, date, hour)
) ENGINE=InnoDB;

INSERT INTO weather_hourly (
    route_code,
    route_name,
    weather_location,
    timestamp_ist,
    date,
    hour,
    day_of_week,
    temperature_2m,
    apparent_temperature,
    relative_humidity_2m,
    precipitation,
    rain,
    weather_code,
    rain_status
)

SELECT
    route_code,
    route,
    weather_location,
    CAST(`timestamp` AS DATETIME),
    CAST(`date` AS DATE),
    CAST(hour AS UNSIGNED),
    day_of_week,
    temperature_2m,
    apparent_temperature,
    relative_humidity_2m,
    precipitation,
    rain,
    weather_code,
    rain_status

FROM weather_aug_sep_import

UNION ALL

SELECT
    route_code,
    route,
    weather_location,
    CAST(`timestamp` AS DATETIME),
    CAST(`date` AS DATE),
    CAST(hour AS UNSIGNED),
    day_of_week,
    temperature_2m,
    apparent_temperature,
    relative_humidity_2m,
    precipitation,
    rain,
    weather_code,
    rain_status

FROM weather_oct_sep_import;


SELECT
    MIN(date) AS start_date,
    MAX(date) AS end_date,
    COUNT(DISTINCT route_code) AS routes
FROM weather_hourly;

# preparing traffic table and routes
ALTER TABLE traffic_readings
MODIFY COLUMN route_code VARCHAR(60) NOT NULL,
MODIFY COLUMN `date` DATE NOT NULL,
MODIFY COLUMN hour TINYINT UNSIGNED NOT NULL;

SHOW INDEX FROM traffic_readings;

#adding primary key for routes table
ALTER TABLE traffic_readings
ADD PRIMARY KEY (route_code, `date`, hour);

# creating routes table
CREATE TABLE routes (
    route_code VARCHAR(60) NOT NULL PRIMARY KEY,
    route_name VARCHAR(100),
    origin_name VARCHAR(150),
    dest_name VARCHAR(150),
    origin_code VARCHAR(30),
    dest_code VARCHAR(30),
    accuweather_station VARCHAR(100),
    map_link VARCHAR(500)
);

INSERT INTO routes (
    route_code,
    route_name,
    origin_name,
    dest_name,
    origin_code,
    dest_code,
    accuweather_station,
    map_link
)

SELECT DISTINCT
    route_code,
    route_name,
    origin_name,
    dest_name,
    origin_code,
    dest_code,
    accuweather_station,
    map_link

FROM traffic_readings;

SELECT COUNT(*) FROM routes;

# preparing metro tables
ALTER TABLE metro_station_hourly
CHANGE COLUMN `Date`
observation_date DATE NOT NULL,
CHANGE COLUMN `Hour`
hour TINYINT UNSIGNED NOT NULL,
CHANGE COLUMN `Station`
station_name VARCHAR(100) NOT NULL,
CHANGE COLUMN `Ridership`
ridership BIGINT UNSIGNED NOT NULL,
CHANGE COLUMN `Exits`
exits BIGINT UNSIGNED NOT NULL;

ALTER TABLE metro_station_hourly
ADD PRIMARY KEY (
    observation_date,
    hour,
    station_name
);

CREATE TABLE metro_stations (
    station_name VARCHAR(100) NOT NULL PRIMARY KEY
);

INSERT INTO metro_stations (station_name)
SELECT DISTINCT station_name
FROM metro_station_hourly;



ALTER TABLE metro_daily_ticket
CHANGE COLUMN `Record Date`
record_date DATE NOT NULL,
CHANGE COLUMN `Day of Week`
day_of_week VARCHAR(15),
CHANGE COLUMN `Traffic Band`
traffic_band VARCHAR(30),
CHANGE COLUMN `Total Smart Cards`
total_smart_cards BIGINT,
CHANGE COLUMN `Stored Value Card`
stored_value_card BIGINT,
CHANGE COLUMN `One Day Pass`
one_day_pass BIGINT,
CHANGE COLUMN `Three Day Pass`
three_day_pass BIGINT,
CHANGE COLUMN `Five Day Pass`
five_day_pass BIGINT,
CHANGE COLUMN `Total QR`
total_qr BIGINT,
CHANGE COLUMN `QR NammaMetro`
qr_nammametro BIGINT,
CHANGE COLUMN `QR WhatsApp`
qr_whatsapp BIGINT,
CHANGE COLUMN `QR Paytm`
qr_paytm BIGINT,
CHANGE COLUMN `QR ONDC`
qr_ondc BIGINT,
CHANGE COLUMN `Total Tokens`
total_tokens BIGINT,
CHANGE COLUMN `Total NCMC`
total_ncmc BIGINT,
CHANGE COLUMN `Group Ticket`
group_ticket BIGINT,
CHANGE COLUMN `Total`
total BIGINT;


# preparing google trends table
ALTER TABLE trends_daily_traffic
MODIFY COLUMN `date` DATE NOT NULL,
MODIFY COLUMN term VARCHAR(100) NOT NULL;

ALTER TABLE trends_daily_metro
MODIFY COLUMN `date` DATE NOT NULL,
MODIFY COLUMN term VARCHAR(100) NOT NULL;

ALTER TABLE trends_daily_traffic
ADD PRIMARY KEY (`date`, term);

ALTER TABLE trends_daily_metro
ADD PRIMARY KEY (`date`, term);


CREATE TABLE calendar (
    calendar_date DATE PRIMARY KEY,
    day_of_week VARCHAR(15),
    weekday_num TINYINT,
    month TINYINT,
    month_name VARCHAR(15),
    is_weekend BOOLEAN,
    is_second_saturday BOOLEAN,
    is_fourth_saturday BOOLEAN,
    is_public_holiday BOOLEAN,
    is_karnataka_govt_general_holiday BOOLEAN,
    holiday_name VARCHAR(120),
    festival_name VARCHAR(120),
    source_note VARCHAR(150),
    is_long_weekend BOOLEAN
);

SELECT COUNT(*) FROM calendar;


# foreign key relationships
ALTER TABLE traffic_readings
ADD CONSTRAINT fk_traffic_route
FOREIGN KEY (route_code)
REFERENCES routes(route_code);

ALTER TABLE weather_hourly
ADD CONSTRAINT fk_weather_route
FOREIGN KEY (route_code)
REFERENCES routes(route_code);

ALTER TABLE metro_station_hourly
ADD CONSTRAINT fk_metro_station
FOREIGN KEY (station_name)
REFERENCES metro_stations(station_name);

ALTER TABLE traffic_readings
ADD CONSTRAINT fk_traffic_calendar
FOREIGN KEY (`date`)
REFERENCES calendar(calendar_date);

ALTER TABLE weather_hourly
ADD CONSTRAINT fk_weather_calendar
FOREIGN KEY (`date`)
REFERENCES calendar(calendar_date);

ALTER TABLE metro_station_hourly
ADD CONSTRAINT fk_metro_hourly_calendar
FOREIGN KEY (observation_date)
REFERENCES calendar(calendar_date);

ALTER TABLE metro_daily_ticket
ADD CONSTRAINT fk_metro_daily_calendar
FOREIGN KEY (record_date)
REFERENCES calendar(calendar_date);

ALTER TABLE trends_daily_traffic
ADD CONSTRAINT fk_trends_traffic_calendar
FOREIGN KEY (`date`)
REFERENCES calendar(calendar_date);

ALTER TABLE trends_daily_metro
ADD CONSTRAINT fk_trends_metro_calendar
FOREIGN KEY (`date`)
REFERENCES calendar(calendar_date);


# views
CREATE OR REPLACE VIEW vw_traffic_weather AS
SELECT
    t.route_code,
    t.route_name,
    t.`date`,
    t.hour,
    t.duration_min,
    t.distance_km,
    t.speed_kmph,
    t.congestion_index,
    t.row_status,
    w.weather_location,
    w.temperature_2m,
    w.apparent_temperature,
    w.relative_humidity_2m,
    w.rain,
    w.precipitation,
    w.weather_code
FROM traffic_readings t
LEFT JOIN weather_hourly w
    ON t.route_code = w.route_code
    AND t.`date` = w.`date`
    AND t.hour = w.hour;
    
SELECT COUNT(*) FROM vw_traffic_weather;

# view 2: Daily Traffic + Google Trends
CREATE OR REPLACE VIEW vw_daily_traffic AS
SELECT
    `date`,
    AVG(
        CASE
            WHEN row_status = 'observed'
            THEN congestion_index
        END
    ) AS avg_observed_congestion,
    AVG(
        CASE
            WHEN row_status = 'observed'
            THEN speed_kmph
        END
    ) AS avg_observed_speed,
    SUM(row_status = 'observed') AS observed_records,
    SUM(row_status = 'interpolated') AS interpolated_records,
    SUM(row_status = 'missing_hour') AS missing_hour_records,
    SUM(row_status = 'observed_dur_interpolated')
        AS observed_duration_interpolated_records
FROM traffic_readings
GROUP BY `date`;

CREATE OR REPLACE VIEW vw_daily_traffic_trends AS

SELECT
    d.`date`,
    d.avg_observed_congestion,
    d.avg_observed_speed,
    g.interest_index,
    g.interest_z,
    g.flag_spike,
    c.is_weekend,
    c.holiday_name,
    c.festival_name
FROM vw_daily_traffic d
LEFT JOIN trends_daily_traffic g
    ON d.`date` = g.`date`
    AND g.term = 'bangalore traffic'
LEFT JOIN calendar c
    ON d.`date` = c.calendar_date;
    

# view 3: Metro Daily Tickets + Traffic
CREATE OR REPLACE VIEW vw_daily_traffic_metro AS
SELECT
    d.`date`,
    d.avg_observed_congestion,
    m.total AS metro_daily_ticket_total,
    m.total_smart_cards,
    m.total_qr,
    m.total_tokens,
    m.total_ncmc
FROM vw_daily_traffic d
INNER JOIN metro_daily_ticket m
    ON d.`date` = m.record_date;
    
SELECT COUNT(*)
FROM vw_daily_traffic_metro;

# View 4: Hourly Metro + Metro Trends
CREATE OR REPLACE VIEW vw_metro_hourly AS
SELECT
    observation_date,
    hour,
    SUM(ridership) AS total_ridership,
    SUM(exits) AS total_exits,
    COUNT(DISTINCT station_name) AS reporting_stations
FROM metro_station_hourly
GROUP BY observation_date, hour;


CREATE OR REPLACE VIEW vw_metro_hourly_trends AS
SELECT
    m.observation_date,
    m.hour,
    m.total_ridership,
    m.total_exits,
    m.reporting_stations,
    g.interest_index AS metro_search_interest
FROM vw_metro_hourly m
LEFT JOIN trends_daily_metro g
    ON m.observation_date = g.`date`
    AND g.term = 'bangalore metro';
    
# view 5: metro ridership
CREATE OR REPLACE VIEW vw_city_weather_hourly AS
SELECT
    `date`,
    hour,
    AVG(temperature_2m) AS avg_temperature,
    AVG(rain) AS avg_rainfall,
    MAX(rain) AS max_rainfall
FROM weather_hourly
WHERE `date` BETWEEN '2025-08-01' AND '2025-09-30'
GROUP BY `date`, hour;


CREATE OR REPLACE VIEW vw_metro_hourly_weather AS
SELECT
    m.observation_date,
    m.hour,
    m.total_ridership,
    m.total_exits,
    m.reporting_stations,
    w.avg_temperature,
    w.avg_rainfall,
    w.max_rainfall
FROM vw_metro_hourly m
LEFT JOIN vw_city_weather_hourly w
    ON m.observation_date = w.`date`
    AND m.hour = w.hour;
    
    
# Query 1: Identify peak traffic hours
SELECT
    weekday,
    hour,
    AVG(congestion_index) AS avg_congestion
FROM traffic_readings
WHERE row_status = 'observed'
GROUP BY weekday, weekday_num, hour
ORDER BY weekday_num, hour;

# Query 2: Identify the most congested routes
SELECT
    route_name,
    AVG(congestion_index) AS avg_congestion,
    AVG(duration_min) AS avg_duration
FROM traffic_readings
WHERE row_status = 'observed'
GROUP BY route_code, route_name
ORDER BY avg_congestion DESC;

# Query 3: Compare rainy and non-rainy traffic
SELECT
    CASE
        WHEN w.rain > 0 THEN 'Rainy'
        ELSE 'Non-Rainy'
    END AS weather_condition,
    AVG(t.congestion_index) AS avg_congestion,
    AVG(t.speed_kmph) AS avg_speed
FROM traffic_readings t
JOIN weather_hourly w
    ON t.route_code = w.route_code
    AND t.`date` = w.`date`
    AND t.hour = w.hour
WHERE t.row_status = 'observed'
GROUP BY weather_condition;

# Query 4: Find the busiest metro stations
SELECT
    station_name,
    SUM(ridership) AS total_ridership,
    SUM(exits) AS total_exits
FROM metro_station_hourly
GROUP BY station_name
ORDER BY total_ridership DESC
LIMIT 10;

# Query 5: Compare traffic and metro ridership
SELECT *
FROM vw_daily_traffic_metro
ORDER BY avg_observed_congestion DESC;

# Query 6: Compare Google Trends interest with congestion
SELECT
    `date`,
    avg_observed_congestion,
    interest_index,
    interest_z
FROM vw_daily_traffic_trends
ORDER BY interest_index DESC;