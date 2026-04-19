import pandas as pd
import os

def generate_report(records, duration, output_path):
    """
    Generates a structured data report (CSV/Excel).
    
    Args:
        records: list of dicts with keys (frame_index, timestamp, track_id, class)
        duration: processing duration in seconds
        output_path: filepath to save the report (e.g., 'report.csv' or 'report.xlsx')
    """
    if not records:
        print("No records to export.")
        df = pd.DataFrame(columns=['frame_index', 'timestamp', 'track_id', 'class'])
    else:
        df = pd.DataFrame(records)
        # Exclude specific columns as requested by the user
        cols_to_exclude = ['confidence', 'detected_at_y']
        df = df.drop(columns=[col for col in cols_to_exclude if col in df.columns], errors='ignore')

    # Convert timestamp to a more readable format if necessary, or keep as float seconds
    df['timestamp'] = df['timestamp'].round(2)

    # Calculate summary
    total_count = len(df)
    breakdown = df['class'].value_counts().to_dict() if not df.empty else {}

    print(f"--- Report Summary ---")
    print(f"Total Vehicles: {total_count}")
    print(f"Breakdown: {breakdown}")
    print(f"Processing Duration: {duration:.2f} seconds")
    print(f"----------------------")

    # Export to chosen format
    if output_path.endswith('.csv'):
        # Write summary headers first
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("--- Report Summary ---\n")
            f.write(f"Total Vehicles,{total_count}\n")
            f.write(f"Processing Duration (s),{duration:.2f}\n")
            breakdown_str = "; ".join([f"{k}: {v}" for k, v in breakdown.items()])
            f.write(f"Breakdown,{breakdown_str}\n")
            f.write("\n")
        # Append the actual frame data
        df.to_csv(output_path, mode='a', index=False)
        
    elif output_path.endswith('.xlsx'):
        # For Excel, we can create an ExcelWriter and write the summary to a different sheet, 
        # or just write the raw data and let the user compute stats. 
        # Writing to two sheets is best.
        with pd.ExcelWriter(output_path) as writer:
            summary_df = pd.DataFrame({
                'Metric': ['Total Vehicles', 'Processing Duration (s)', 'Breakdown'],
                'Value': [total_count, f"{duration:.2f}", "; ".join([f"{k}: {v}" for k, v in breakdown.items()])]
            })
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            df.to_excel(writer, sheet_name='Detections', index=False)
            
    else:
        # Default to CSV if extension is unknown
        with open(output_path + '.csv', 'w', encoding='utf-8') as f:
            f.write("--- Report Summary ---\n")
            f.write(f"Total Vehicles,{total_count}\n")
            f.write(f"Processing Duration (s),{duration:.2f}\n")
            breakdown_str = "; ".join([f"{k}: {v}" for k, v in breakdown.items()])
            f.write(f"Breakdown,{breakdown_str}\n")
            f.write("\n")
        df.to_csv(output_path + '.csv', mode='a', index=False)
