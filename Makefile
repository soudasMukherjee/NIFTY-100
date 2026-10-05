.PHONY: load validate test report dashboard api clean

load:
	python3 src/etl/loader.py

validate:
	python3 src/etl/validator.py

test:
	python3 -m pytest tests/ -v

report: load validate
	@echo "load_audit.csv and validation_failures.csv regenerated in output/"

dashboard:
	streamlit run app.py

api:
	uvicorn src.api.main:app --reload --port 8000

clean:
	rm -f nifty100.db
	rm -f output/*.csv
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
