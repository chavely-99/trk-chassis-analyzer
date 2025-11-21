# TRK Chassis Analyzer

A Streamlit application for analyzing suspension damper lengths and optimizing chassis configurations.

## Features

- **Data Configuration**: Upload Excel files with suspension geometry data
- **Damper Length Calculations**: Calculate damper lengths based on upper/lower mount positions
- **LCA Z Height Normalization**: Option to normalize lower control arm Z heights to median for realistic calculations
- **Rankings & Analysis**: View rankings for individual corners (LF, RF, LR, RR) and overall front/rear performance
- **Scatter Analysis**: Visualize damper length distributions with filtering options
- **Attribute Compare**: Analyze correlations between assembly variables and damper lengths
- **Lineup Builder**: Optimize clip assignments to center sections with customizable corner weightings
- **Track Type Classification**: Assign track types (INT, ST, RC, Utility, SSW, Backup) to each configuration

## Usage

1. Upload your Excel file containing suspension geometry data
2. Configure column mappings for upper mounts, LCA points, and offsets
3. Calculate damper lengths
4. Explore rankings, scatter plots, and optimize your lineup

## Deployment

This app is designed to run on Streamlit Community Cloud.
