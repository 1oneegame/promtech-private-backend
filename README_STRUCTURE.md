# IntegrityOS - Pipeline Defect Inspection System

REST API for analyzing pipeline defects from ILI (In-Line Inspection) data.

## Project Structure

```
terricon/
├── main.py                 # Entry point - run this to start the API
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── docker-compose.yml     # Docker configuration
├── Dockerfile             # Container image definition
│
├── src/                   # Source code
│   ├── app.py            # FastAPI application & endpoints
│   ├── models.py         # Pydantic data models
│   ├── parser.py         # CSV parser
│   └── database.py       # Database layer
│
├── config/               # Configuration files
│   ├── config.py        # App configuration
│   └── .env.example     # Environment variables template
│
├── data/                # CSV data files
│   └── Svodny_Otchet_ILI_Clean.csv
│
├── output/              # Generated output files
│   ├── defects_output.json
│   └── defects_parsed.json
│
├── logs/                # Log files
│   └── parser.log
│
└── venv/                # Python virtual environment (not in repo)
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the API
```bash
python main.py
```

The API will be available at: http://localhost:8000

### 3. API Documentation
Interactive docs: http://localhost:8000/docs

## API Endpoints

### Get All Defects
```
GET /defects
```

### Search with Multiple Filters
```
GET /defects/search?severity=high&defect_type=коррозия&segment=3
```

Query parameters:
- `severity`: normal, high, critical
- `defect_type`: коррозия, сварной шов, металлический объект
- `segment`: segment number (integer)

### Filter by Single Criteria
```
GET /defects/severity/{severity}
GET /defects/type/{defect_type}
GET /defects/segment/{segment_id}
```

### Get Statistics
```
GET /statistics
```

### Export Data
```
GET /export/json
```

## Data Format

Each defect contains:
- `defect_id`: Unique identifier
- `segment_number`: Pipeline segment
- `measurement_distance_m`: Distance in meters
- `pipeline_id`: Pipeline identifier
- `details`: Contains type, parameters, location, surface location, distance to weld, ERF B31G code

## Docker Deployment

Build and run with Docker:
```bash
docker-compose up -d
```

## Configuration

Edit `config/config.py` for application settings.

## Logging

Logs are saved to `logs/parser.log`

Output data is saved to `output/` directory as JSON files.
