from google.cloud import bigquery
client = bigquery.Client(project="pi-intake-forecast")
print(list(client.query("SELECT 'BigQuery connected' AS status").result())[0].status)