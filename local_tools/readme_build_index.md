# Build the Guidance Index (offline)

1) Install deps locally:
   ```
   pip install -r requirements.txt
   ```

2) Run:
   ```
   python local_tools/index_builder.py --root "C:\\Mac\\Home\\Music\\Guidance" --out guidance_index
   ```

3) You’ll get:
   - `guidance_index.faiss`
   - `guidance_index.pkl`

4) In the Streamlit app (Settings tab), upload both files and click **Load Index**.
