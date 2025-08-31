# Seker V2 — AI Design Quality Auditor (Starter)

## How to run
1. `pip install -r requirements.txt`
2. `streamlit run app.py`

## First steps
- Open **Settings** → enter your **Guidance root path** (e.g. `C:\Mac\Home\Music\Guidance`) and click **Reload guidance index**.
- Guidance is **mandatory** before audits.

## Training / Learning
- In the **Audit** tab, after results appear, mark each finding as **Keep** or **False positive** and click **Apply Feedback**.
- Spelling false-positives will be remembered per context (client/project/vendor/site_type).
- Add new rules in **Training → Quick Rule Builder** or edit YAML in **Settings**.
