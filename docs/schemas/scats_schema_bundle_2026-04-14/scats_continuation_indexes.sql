┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                             sql                                              │
│                                           varchar                                            │
├──────────────────────────────────────────────────────────────────────────────────────────────┤
│ CREATE INDEX idx_scats_detector_day_date ON scats_detector_day(count_date);                  │
│ CREATE INDEX idx_scats_detector_day_site ON scats_detector_day(scats_site);                  │
│ CREATE INDEX idx_scats_detector_day_site_date ON scats_detector_day(scats_site, count_date); │
│ CREATE INDEX idx_scats_site_latlon ON scats_site(latitude, longitude);                       │
│ CREATE INDEX idx_scats_site_municipality ON scats_site(municipality);                        │
│ CREATE INDEX idx_source_file_date ON source_file(file_date);                                 │
│ CREATE INDEX idx_source_file_status ON source_file(load_status);                             │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
