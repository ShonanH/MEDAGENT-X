# Prepare Full CheXpert Plus DICOM Training Data

Run from the repository root on the JupyterHub machine that will store the
dataset.

```bash
export PYTHONPATH="v2/src${PYTHONPATH:+:${PYTHONPATH}}"
export REDIVIS_API_TOKEN="YOUR_REDIVIS_API_TOKEN"
```

Check available storage before starting:

```bash
df -h v2/artifacts
```

Fetch all downloadable CheXpert Plus train metadata, apply the existing label
gate, and download the resulting DICOMs:

```bash
python -m medagentx.cli.fetch_stage_a_data \
  --output-root v2/artifacts/cohort_full \
  --skip-reports \
  --download-workers 8 \
  --progress-every 250
```

Do not pass `--max-patients`, `--max-studies`, `--max-rows`,
`--metadata-limit`, or `--index-limit`; those options are development caps.

The command is restartable. Completed files remain in
`v2/artifacts/cohort_full/dicom_train/`, incomplete transfers remain as
`.part` files, and rerunning the same command resumes those transfers.

The download is the first preparation stage only. Pixel quality filtering,
patient-level split construction, study-label finalization, and full-data
training are separate stages and should be configured after the download
inventory is known.
