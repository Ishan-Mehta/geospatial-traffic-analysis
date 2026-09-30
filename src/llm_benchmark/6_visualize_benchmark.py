import os
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from config import (
    COMPARISON_RESULTS_DIR,
    CHARTS_DIR
)

def main():
    print("Starting visualizations...")
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    
    comp_file = COMPARISON_RESULTS_DIR / 'benchmark_comparison.csv'
    if not comp_file.exists():
        print(f"Error: {comp_file} not found. Run compare_results.py first.")
        return
        
    df = pd.read_csv(comp_file)
    
    if df.empty:
        print("Error: DataFrame is empty.")
        return

    # Add useful derived columns
    df['gmaps_live_min'] = df['gmaps_live_s'] / 60.0
    df['gmaps_dist_km'] = df['gmaps_dist_m'] / 1000.0

    sns.set_theme(style="whitegrid")

    # 1. scatter_llm_vs_gmaps_time.png
    print("Generating scatter_llm_vs_gmaps_time.png...")
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='llm_time_min', y='gmaps_live_min', hue='category', s=60, alpha=0.7)
    max_val = max(df['llm_time_min'].max(), df['gmaps_live_min'].max())
    plt.plot([0, max_val], [0, max_val], 'k--', zorder=-1) # y=x reference line
    plt.title('LLM Estimated Time vs GMaps Live Time')
    plt.xlabel('LLM Estimated Time (min)')
    plt.ylabel('GMaps Live Time (min)')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'scatter_llm_vs_gmaps_time.png', bbox_inches='tight')
    plt.close()

    # 2. scatter_llm_vs_gmaps_distance.png
    print("Generating scatter_llm_vs_gmaps_distance.png...")
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df, x='llm_dist_km', y='gmaps_dist_km', hue='category', s=60, alpha=0.7)
    max_val = max(df['llm_dist_km'].max(), df['gmaps_dist_km'].max())
    plt.plot([0, max_val], [0, max_val], 'k--', zorder=-1) # y=x reference line
    plt.title('LLM Estimated Distance vs GMaps Distance')
    plt.xlabel('LLM Estimated Distance (km)')
    plt.ylabel('GMaps Distance (km)')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'scatter_llm_vs_gmaps_distance.png', bbox_inches='tight')
    plt.close()

    # 3. bar_error_by_category.png
    print("Generating bar_error_by_category.png...")
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # Time error
    sns.barplot(data=df, x='category', y='abs_time_error_min', errorbar=None, ax=axes[0])
    axes[0].set_title('Mean Absolute Time Error by Category')
    axes[0].set_ylabel('Absolute Time Error (min)')
    axes[0].tick_params(axis='x', rotation=45)
    
    # Distance error
    sns.barplot(data=df, x='category', y='abs_dist_error_km', errorbar=None, ax=axes[1])
    axes[1].set_title('Mean Absolute Distance Error by Category')
    axes[1].set_ylabel('Absolute Distance Error (km)')
    axes[1].tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'bar_error_by_category.png', bbox_inches='tight')
    plt.close()

    # 4. bar_error_by_timeslot.png
    print("Generating bar_error_by_timeslot.png...")
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x='time_slot', y='abs_time_error_min', errorbar=None)
    plt.title('Mean Absolute Time Error by Time Slot')
    plt.xlabel('Time Slot')
    plt.ylabel('Absolute Time Error (min)')
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'bar_error_by_timeslot.png')
    plt.close()

    # 5. box_time_error_distribution.png
    print("Generating box_time_error_distribution.png...")
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='category', y='time_vs_live_error_pct')
    plt.title('Time vs Live Error % Distribution by Category')
    plt.xlabel('Category')
    plt.ylabel('Time Error vs Live (%)')
    plt.xticks(rotation=45)
    plt.axhline(0, color='k', linestyle='--', zorder=-1)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'box_time_error_distribution.png')
    plt.close()

    # 6. heatmap_error_by_slot_category.png
    print("Generating heatmap_error_by_slot_category.png...")
    plt.figure(figsize=(10, 6))
    pivot_df = df.pivot_table(values='time_vs_live_error_pct', index='time_slot', columns='category', aggfunc='mean')
    sns.heatmap(pivot_df, annot=True, cmap='coolwarm', center=0, fmt='.1f')
    plt.title('Mean Time Error (%) by Time Slot and Category')
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / 'heatmap_error_by_slot_category.png')
    plt.close()
    
    print("All charts generated successfully.")

if __name__ == "__main__":
    main()
