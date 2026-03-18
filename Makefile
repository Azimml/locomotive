run:
	.venv/bin/uvicorn app.main:app --reload --port 8000

update:
	.venv/bin/python -c "from app.sources.api import update_dataset_cache; r = update_dataset_cache(); print(f'Updated: {r[\"record_count\"]} records, {r[\"work_info_count\"]} work, {r[\"count_emm_count\"]} emm, {r[\"med_data_count\"]} med')"

refresh:
	.venv/bin/python -c "from app.sources.api import refresh_dataset_cache; r = refresh_dataset_cache(); print(f'Refreshed: {r[\"record_count\"]} records, {r[\"work_info_count\"]} work, {r[\"count_emm_count\"]} emm, {r[\"med_data_count\"]} med')"
