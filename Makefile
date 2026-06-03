test:
	python3 -B -m unittest discover -s tests

stats:
	python3 -B -m industry_radar stats

report:
	python3 -B -m industry_radar report --top 5 --output outputs/top5_report.md

pipeline-dry-run:
	python3 -B -m industry_radar pipeline --sources data/sources.json --limit 3 --top 5

clean:
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	find . -name "*.pyc" -delete
