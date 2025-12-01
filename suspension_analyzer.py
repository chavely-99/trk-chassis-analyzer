import streamlit as st
import pandas as pd
import numpy as np
from io import StringIO
import json
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(
    page_title="TRK Chassis Analyzer",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

# Reduce top padding and margins
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 0rem;
        }
        footer {
            visibility: hidden;
        }
        /* Reduce whitespace around plotly charts */
        .js-plotly-plot, .plot-container {
            margin-top: -0.5rem !important;
        }
        div[data-testid="stPlotlyChart"] {
            margin-top: -0.5rem !important;
        }
    </style>
    """, unsafe_allow_html=True)

st.markdown("# TRK Chassis Analyzer")
st.markdown("")

# Initialize variables
uploaded_file = None
calculate_button = False
df = None

# Top-level tabs: Data Configuration and Analysis
config_tab, analysis_tab = st.tabs(["📁 Data Configuration", "📊 Analysis"])

with config_tab:
    st.header("Data Configuration")
    st.caption("Upload your data file and configure column mappings")

    uploaded_file = st.file_uploader("Upload your survey data (CSV or Excel)", type=['csv', 'xlsx', 'xls'])

    if uploaded_file is not None:
        try:
            # Load file
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
                sheet_names = None
            else:
                # For Excel files, read all sheet names first
                excel_file = pd.ExcelFile(uploaded_file)
                sheet_names = excel_file.sheet_names

                # If multiple sheets, let user select
                if len(sheet_names) > 1:
                    st.info(f"📋 Excel file contains {len(sheet_names)} sheets: {', '.join(sheet_names)}")

                    sheet_cols = st.columns(2)
                    with sheet_cols[0]:
                        front_sheet = st.selectbox("Front Clip Data Sheet", options=sheet_names, index=0, key='front_sheet_select')
                    with sheet_cols[1]:
                        rear_sheet = st.selectbox("Rear Clip Data Sheet", options=sheet_names, index=min(1, len(sheet_names)-1), key='rear_sheet_select')

                    # Read the selected sheets
                    df_front = pd.read_excel(uploaded_file, sheet_name=front_sheet)
                    df_rear = pd.read_excel(uploaded_file, sheet_name=rear_sheet)

                    # Store both dataframes
                    st.session_state['df_front'] = df_front
                    st.session_state['df_rear'] = df_rear
                    st.session_state['using_multi_sheet'] = True

                    st.success(f"✅ Loaded Front: {len(df_front)} rows, Rear: {len(df_rear)} rows")

                    # For initial configuration, use front sheet columns
                    df = df_front
                else:
                    # Single sheet - use it for everything
                    df = pd.read_excel(uploaded_file, sheet_name=sheet_names[0])
                    st.session_state['using_multi_sheet'] = False
                    st.success(f"✅ Loaded {len(df)} combinations from '{sheet_names[0]}'")

            # Put all configuration in a collapsible expander
            with st.expander("⚙️ Column Mapping & Configuration - Click to Configure", expanded=False):

                # Helper functions
                def filter_cols(df, axis):
                    """Filter columns that contain the axis letter (case insensitive)"""
                    return [col for col in df.columns if axis.lower() in col.lower()]

                def filter_cols_by_corner(df, axis, corner):
                    """Filter columns by axis (x/y/z) AND corner (LF/RF/LR/RR)"""
                    axis_filtered = filter_cols(df, axis)
                    corner_lower = corner.lower()

                    # Check for exact corner match (LF, RF, LR, RR)
                    corner_filtered = [col for col in axis_filtered if corner_lower in col.lower()]

                    # Also check for left/right if no exact match
                    if not corner_filtered:
                        if corner in ['LF', 'LR']:
                            corner_filtered = [col for col in axis_filtered if 'left' in col.lower()]
                        elif corner in ['RF', 'RR']:
                            corner_filtered = [col for col in axis_filtered if 'right' in col.lower()]

                    return corner_filtered if corner_filtered else axis_filtered

                x_cols = filter_cols(df, 'x')
                y_cols = filter_cols(df, 'y')
                z_cols = filter_cols(df, 'z')
                all_cols = list(df.columns)

                # Helper function to filter LCA columns
                def filter_lca_cols(df, axis):
                    """Filter columns that contain both 'lca' and the axis letter"""
                    return [col for col in df.columns if 'lca' in col.lower() and axis.lower() in col.lower()]

                lca_x_cols = filter_lca_cols(df, 'x')
                lca_y_cols = filter_lca_cols(df, 'y')
                lca_z_cols = filter_lca_cols(df, 'z')

                # Helper function to filter front/rear columns
                def filter_front_cols(cols):
                    """Filter columns that contain 'front' or 'frt' or 'f' indicators"""
                    return [col for col in cols if any(indicator in col.lower() for indicator in ['front', 'frt', '_f_', '_f'])]

                def filter_rear_cols(cols):
                    """Filter columns that contain 'rear' or 'rr' or 'r' indicators"""
                    return [col for col in cols if any(indicator in col.lower() for indicator in ['rear', 'rr', '_r_', '_r'])]

                def filter_right_cols(cols):
                    """Filter columns that contain 'right' or 'rf' or 'rr' indicators"""
                    return [col for col in cols if 'right' in col.lower()]

                # Front LCA columns
                lca_front_x_cols = filter_front_cols(lca_x_cols) if filter_front_cols(lca_x_cols) else lca_x_cols
                lca_front_y_cols = filter_front_cols(lca_y_cols) if filter_front_cols(lca_y_cols) else lca_y_cols
                lca_front_z_cols = filter_front_cols(lca_z_cols) if filter_front_cols(lca_z_cols) else lca_z_cols

                # Rear LCA columns
                lca_rear_x_cols = filter_rear_cols(lca_x_cols) if filter_rear_cols(lca_x_cols) else lca_x_cols
                lca_rear_y_cols = filter_rear_cols(lca_y_cols) if filter_rear_cols(lca_y_cols) else lca_y_cols
                lca_rear_z_cols = filter_rear_cols(lca_z_cols) if filter_rear_cols(lca_z_cols) else lca_z_cols

                # Column mapping
                st.markdown("---")
                st.subheader("📍 Column Mapping")

                # Check if we have a loaded config
                loaded_config = st.session_state.get('loaded_config', {})

                # Helper to get index from config
                def get_index(col_name, col_list, default=0):
                    if col_name in loaded_config and loaded_config[col_name] in col_list:
                        return col_list.index(loaded_config[col_name])
                    return default

                # Helper to get value from config for number inputs
                def get_value(param_name, default=0.0):
                    if param_name in loaded_config:
                        return loaded_config[param_name]
                    return default

                st.markdown("**Vehicle Configuration**")
                center_section_col = st.selectbox("Center Section", options=all_cols, index=get_index('center_section_col', all_cols, 0))
                clip_col = st.selectbox("Clip", options=all_cols, index=get_index('clip_col', all_cols, 1 if len(all_cols) > 1 else 0))

                st.markdown("---")

                # Coordinate selection expander with tabs
                with st.expander("📍 Corner Coordinates - Click to Configure", expanded=False):
                    front_tab, rear_tab = st.tabs(["🏎️ Front Clip (LF/RF)", "🏎️ Rear Clip (LR/RR)"])

                    # FRONT CLIP TAB
                    with front_tab:
                        st.markdown("##### **↑ Front of Car ↑**")

                        # FRONT UPPER DAMPER MOUNTS
                        st.markdown("**Upper Damper Mounts (Front)**")
                        front_upper = st.columns([0.5, 1, 1, 0.5])

                        with front_upper[1]:
                            st.markdown("**🔵 LF Upper**")
                            x_options = x_cols if x_cols else all_cols
                            y_options = y_cols if y_cols else all_cols
                            z_options = z_cols if z_cols else all_cols
                            lf_upper_x = st.selectbox("X", options=x_options, index=get_index('lf_upper_x', x_options, 0), key='lf_ux')
                            lf_upper_y = st.selectbox("Y", options=y_options, index=get_index('lf_upper_y', y_options, 0), key='lf_uy')
                            lf_upper_z = st.selectbox("Z", options=z_options, index=get_index('lf_upper_z', z_options, 0), key='lf_uz')

                        with front_upper[2]:
                            st.markdown("**🔵 RF Upper**")
                            rf_x_options = filter_right_cols(x_options) if filter_right_cols(x_options) else x_options
                            rf_y_options = filter_right_cols(y_options) if filter_right_cols(y_options) else y_options
                            rf_z_options = filter_right_cols(z_options) if filter_right_cols(z_options) else z_options
                            rf_upper_x = st.selectbox("X", options=rf_x_options, index=get_index('rf_upper_x', rf_x_options, 0), key='rf_ux')
                            rf_upper_y = st.selectbox("Y", options=rf_y_options, index=get_index('rf_upper_y', rf_y_options, 0), key='rf_uy')
                            rf_upper_z = st.selectbox("Z", options=rf_z_options, index=get_index('rf_upper_z', rf_z_options, 0), key='rf_uz')

                        st.markdown("")

                        # FRONT LCA
                        st.markdown("**Lower Control Arm Mounts (Front)**")
                        st.caption("Select both front and rear mounting points - they will be averaged")
                        front_lca = st.columns([0.5, 1, 1, 0.5])

                        with front_lca[1]:
                            st.markdown("**🟢 LF LCA Front**")
                            lf_lca_front_x = st.selectbox("X", options=lca_front_x_cols if lca_front_x_cols else all_cols, key='lf_lca_front_x')
                            lf_lca_front_y = st.selectbox("Y", options=lca_front_y_cols if lca_front_y_cols else all_cols, key='lf_lca_front_y')
                            lf_lca_front_z = st.selectbox("Z", options=lca_front_z_cols if lca_front_z_cols else all_cols, key='lf_lca_front_z')

                            st.markdown("**🟢 LF LCA Rear**")
                            lf_lca_rear_x = st.selectbox("X", options=lca_rear_x_cols if lca_rear_x_cols else all_cols, key='lf_lca_rear_x')
                            lf_lca_rear_y = st.selectbox("Y", options=lca_rear_y_cols if lca_rear_y_cols else all_cols, key='lf_lca_rear_y')
                            lf_lca_rear_z = st.selectbox("Z", options=lca_rear_z_cols if lca_rear_z_cols else all_cols, key='lf_lca_rear_z')

                        with front_lca[2]:
                            st.markdown("**🟢 RF LCA Front**")
                            rf_lca_front_x_opts = filter_right_cols(lca_front_x_cols) if filter_right_cols(lca_front_x_cols) else (lca_front_x_cols if lca_front_x_cols else all_cols)
                            rf_lca_front_y_opts = filter_right_cols(lca_front_y_cols) if filter_right_cols(lca_front_y_cols) else (lca_front_y_cols if lca_front_y_cols else all_cols)
                            rf_lca_front_z_opts = filter_right_cols(lca_front_z_cols) if filter_right_cols(lca_front_z_cols) else (lca_front_z_cols if lca_front_z_cols else all_cols)
                            rf_lca_front_x = st.selectbox("X", options=rf_lca_front_x_opts, key='rf_lca_front_x')
                            rf_lca_front_y = st.selectbox("Y", options=rf_lca_front_y_opts, key='rf_lca_front_y')
                            rf_lca_front_z = st.selectbox("Z", options=rf_lca_front_z_opts, key='rf_lca_front_z')

                            st.markdown("**🟢 RF LCA Rear**")
                            rf_lca_rear_x_opts = filter_right_cols(lca_rear_x_cols) if filter_right_cols(lca_rear_x_cols) else (lca_rear_x_cols if lca_rear_x_cols else all_cols)
                            rf_lca_rear_y_opts = filter_right_cols(lca_rear_y_cols) if filter_right_cols(lca_rear_y_cols) else (lca_rear_y_cols if lca_rear_y_cols else all_cols)
                            rf_lca_rear_z_opts = filter_right_cols(lca_rear_z_cols) if filter_right_cols(lca_rear_z_cols) else (lca_rear_z_cols if lca_rear_z_cols else all_cols)
                            rf_lca_rear_x = st.selectbox("X", options=rf_lca_rear_x_opts, key='rf_lca_rear_x')
                            rf_lca_rear_y = st.selectbox("Y", options=rf_lca_rear_y_opts, key='rf_lca_rear_y')
                            rf_lca_rear_z = st.selectbox("Z", options=rf_lca_rear_z_opts, key='rf_lca_rear_z')

                        st.markdown("---")

                        # Front Y-displacement input
                        st.markdown("**⚙️ Lower Damper Mount Y-Offset (Outboard Distance)**")
                        st.caption("Enter positive values - the app automatically applies outboard direction")
                        offset_front = st.columns([0.5, 1, 1, 0.5])
                        with offset_front[1]:
                            lf_y_offset = st.number_input("LF Y Offset", value=get_value('lf_y_offset', 12.1), format="%.4f", key='lf_offset', min_value=0.0)
                        with offset_front[2]:
                            rf_y_offset = st.number_input("RF Y Offset", value=get_value('rf_y_offset', 12.6), format="%.4f", key='rf_offset', min_value=0.0)

                    # REAR CLIP TAB
                    with rear_tab:
                        st.markdown("##### **↓ Rear of Car ↓**")

                        # REAR UPPER DAMPER MOUNTS
                        st.markdown("**Upper Damper Mounts (Rear)**")
                        rear_upper = st.columns([0.5, 1, 1, 0.5])

                        with rear_upper[1]:
                            st.markdown("**🔵 LR Upper**")
                            lr_upper_x = st.selectbox("X", options=x_options, index=get_index('lr_upper_x', x_options, 0), key='lr_ux')
                            lr_upper_y = st.selectbox("Y", options=y_options, index=get_index('lr_upper_y', y_options, 0), key='lr_uy')
                            lr_upper_z = st.selectbox("Z", options=z_options, index=get_index('lr_upper_z', z_options, 0), key='lr_uz')

                        with rear_upper[2]:
                            st.markdown("**🔵 RR Upper**")
                            rr_x_options = filter_right_cols(x_options) if filter_right_cols(x_options) else x_options
                            rr_y_options = filter_right_cols(y_options) if filter_right_cols(y_options) else y_options
                            rr_z_options = filter_right_cols(z_options) if filter_right_cols(z_options) else z_options
                            rr_upper_x = st.selectbox("X", options=rr_x_options, index=get_index('rr_upper_x', rr_x_options, 0), key='rr_ux')
                            rr_upper_y = st.selectbox("Y", options=rr_y_options, index=get_index('rr_upper_y', rr_y_options, 0), key='rr_uy')
                            rr_upper_z = st.selectbox("Z", options=rr_z_options, index=get_index('rr_upper_z', rr_z_options, 0), key='rr_uz')

                        st.markdown("")

                        # REAR LCA
                        st.markdown("**Lower Control Arm Mounts (Rear)**")
                        st.caption("Select both front and rear mounting points - they will be averaged")
                        rear_lca = st.columns([0.5, 1, 1, 0.5])

                        with rear_lca[1]:
                            st.markdown("**🟢 LR LCA Front**")
                            lr_lca_front_x = st.selectbox("X", options=lca_front_x_cols if lca_front_x_cols else all_cols, key='lr_lca_front_x')
                            lr_lca_front_y = st.selectbox("Y", options=lca_front_y_cols if lca_front_y_cols else all_cols, key='lr_lca_front_y')
                            lr_lca_front_z = st.selectbox("Z", options=lca_front_z_cols if lca_front_z_cols else all_cols, key='lr_lca_front_z')

                            st.markdown("**🟢 LR LCA Rear**")
                            lr_lca_rear_x = st.selectbox("X", options=lca_rear_x_cols if lca_rear_x_cols else all_cols, key='lr_lca_rear_x')
                            lr_lca_rear_y = st.selectbox("Y", options=lca_rear_y_cols if lca_rear_y_cols else all_cols, key='lr_lca_rear_y')
                            lr_lca_rear_z = st.selectbox("Z", options=lca_rear_z_cols if lca_rear_z_cols else all_cols, key='lr_lca_rear_z')

                        with rear_lca[2]:
                            st.markdown("**🟢 RR LCA Front**")
                            rr_lca_front_x_opts = filter_right_cols(lca_front_x_cols) if filter_right_cols(lca_front_x_cols) else (lca_front_x_cols if lca_front_x_cols else all_cols)
                            rr_lca_front_y_opts = filter_right_cols(lca_front_y_cols) if filter_right_cols(lca_front_y_cols) else (lca_front_y_cols if lca_front_y_cols else all_cols)
                            rr_lca_front_z_opts = filter_right_cols(lca_front_z_cols) if filter_right_cols(lca_front_z_cols) else (lca_front_z_cols if lca_front_z_cols else all_cols)
                            rr_lca_front_x = st.selectbox("X", options=rr_lca_front_x_opts, key='rr_lca_front_x')
                            rr_lca_front_y = st.selectbox("Y", options=rr_lca_front_y_opts, key='rr_lca_front_y')
                            rr_lca_front_z = st.selectbox("Z", options=rr_lca_front_z_opts, key='rr_lca_front_z')

                            st.markdown("**🟢 RR LCA Rear**")
                            rr_lca_rear_x_opts = filter_right_cols(lca_rear_x_cols) if filter_right_cols(lca_rear_x_cols) else (lca_rear_x_cols if lca_rear_x_cols else all_cols)
                            rr_lca_rear_y_opts = filter_right_cols(lca_rear_y_cols) if filter_right_cols(lca_rear_y_cols) else (lca_rear_y_cols if lca_rear_y_cols else all_cols)
                            rr_lca_rear_z_opts = filter_right_cols(lca_rear_z_cols) if filter_right_cols(lca_rear_z_cols) else (lca_rear_z_cols if lca_rear_z_cols else all_cols)
                            rr_lca_rear_x = st.selectbox("X", options=rr_lca_rear_x_opts, key='rr_lca_rear_x')
                            rr_lca_rear_y = st.selectbox("Y", options=rr_lca_rear_y_opts, key='rr_lca_rear_y')
                            rr_lca_rear_z = st.selectbox("Z", options=rr_lca_rear_z_opts, key='rr_lca_rear_z')

                        st.markdown("---")

                        # Rear Y-displacement input
                        st.markdown("**⚙️ Lower Damper Mount Y-Offset (Outboard Distance)**")
                        st.caption("Enter positive values - the app automatically applies outboard direction")
                        offset_rear = st.columns([0.5, 1, 1, 0.5])
                        with offset_rear[1]:
                            lr_y_offset = st.number_input("LR Y Offset", value=get_value('lr_y_offset', 14.5), format="%.4f", key='lr_offset', min_value=0.0)
                        with offset_rear[2]:
                            rr_y_offset = st.number_input("RR Y Offset", value=get_value('rr_y_offset', 15.6), format="%.4f", key='rr_offset', min_value=0.0)

                st.markdown("---")

                # Save/Load Configuration
                st.subheader("💾 Configuration")
                config_cols = st.columns(2)

                with config_cols[0]:
                    # Save configuration
                    config_data = {
                        "center_section_col": center_section_col,
                        "clip_col": clip_col,
                        "lf_upper_x": lf_upper_x, "lf_upper_y": lf_upper_y, "lf_upper_z": lf_upper_z,
                        "rf_upper_x": rf_upper_x, "rf_upper_y": rf_upper_y, "rf_upper_z": rf_upper_z,
                        "lr_upper_x": lr_upper_x, "lr_upper_y": lr_upper_y, "lr_upper_z": lr_upper_z,
                        "rr_upper_x": rr_upper_x, "rr_upper_y": rr_upper_y, "rr_upper_z": rr_upper_z,
                        "lf_lca_front_x": lf_lca_front_x, "lf_lca_front_y": lf_lca_front_y, "lf_lca_front_z": lf_lca_front_z,
                        "lf_lca_rear_x": lf_lca_rear_x, "lf_lca_rear_y": lf_lca_rear_y, "lf_lca_rear_z": lf_lca_rear_z,
                        "rf_lca_front_x": rf_lca_front_x, "rf_lca_front_y": rf_lca_front_y, "rf_lca_front_z": rf_lca_front_z,
                        "rf_lca_rear_x": rf_lca_rear_x, "rf_lca_rear_y": rf_lca_rear_y, "rf_lca_rear_z": rf_lca_rear_z,
                        "lr_lca_front_x": lr_lca_front_x, "lr_lca_front_y": lr_lca_front_y, "lr_lca_front_z": lr_lca_front_z,
                        "lr_lca_rear_x": lr_lca_rear_x, "lr_lca_rear_y": lr_lca_rear_y, "lr_lca_rear_z": lr_lca_rear_z,
                        "rr_lca_front_x": rr_lca_front_x, "rr_lca_front_y": rr_lca_front_y, "rr_lca_front_z": rr_lca_front_z,
                        "rr_lca_rear_x": rr_lca_rear_x, "rr_lca_rear_y": rr_lca_rear_y, "rr_lca_rear_z": rr_lca_rear_z,
                        "lf_y_offset": lf_y_offset, "rf_y_offset": rf_y_offset,
                        "lr_y_offset": lr_y_offset, "rr_y_offset": rr_y_offset
                    }

                    config_json = json.dumps(config_data, indent=2)
                    st.download_button(
                        label="📥 Save Column Mapping",
                        data=config_json,
                        file_name="trk_chassis_config.json",
                        mime="application/json",
                        help="Download current column mapping configuration"
                    )

                with config_cols[1]:
                    # Load configuration
                    uploaded_config = st.file_uploader(
                        "📤 Load Column Mapping",
                        type=['json'],
                        help="Upload a previously saved configuration",
                        key='config_uploader'
                    )

                    if uploaded_config is not None:
                        try:
                            loaded_config = json.load(uploaded_config)
                            st.success("✅ Configuration loaded! Please rerun to apply.")
                            st.info("Note: Loaded config will apply on next interaction")
                            # Store in session state for next render
                            st.session_state['loaded_config'] = loaded_config
                        except Exception as e:
                            st.error(f"❌ Error loading config: {str(e)}")

            # Calculate button - outside the expander
            st.markdown("---")

            # Normalize LCA Z Heights option
            normalize_lca_z = st.checkbox(
                "Normalize LCA Z Heights",
                value=True,
                help="Set all lower control arm Z heights to the median value for more realistic damper travel calculations"
            )

            calculate_button = st.button("🔬 Calculate Damper Lengths & Travel", type="primary", use_container_width=True)

            # Store configuration in session state when button is clicked
            if calculate_button:
                # Store column names for use in Analysis tab
                st.session_state['center_section_col'] = center_section_col
                st.session_state['clip_col'] = clip_col

                st.session_state['config'] = {
                    'center_section_col': center_section_col,
                    'clip_col': clip_col,
                    'lf_upper_x': lf_upper_x, 'lf_upper_y': lf_upper_y, 'lf_upper_z': lf_upper_z,
                    'rf_upper_x': rf_upper_x, 'rf_upper_y': rf_upper_y, 'rf_upper_z': rf_upper_z,
                    'lr_upper_x': lr_upper_x, 'lr_upper_y': lr_upper_y, 'lr_upper_z': lr_upper_z,
                    'rr_upper_x': rr_upper_x, 'rr_upper_y': rr_upper_y, 'rr_upper_z': rr_upper_z,
                    'lf_lca_front_x': lf_lca_front_x, 'lf_lca_front_y': lf_lca_front_y, 'lf_lca_front_z': lf_lca_front_z,
                    'lf_lca_rear_x': lf_lca_rear_x, 'lf_lca_rear_y': lf_lca_rear_y, 'lf_lca_rear_z': lf_lca_rear_z,
                    'rf_lca_front_x': rf_lca_front_x, 'rf_lca_front_y': rf_lca_front_y, 'rf_lca_front_z': rf_lca_front_z,
                    'rf_lca_rear_x': rf_lca_rear_x, 'rf_lca_rear_y': rf_lca_rear_y, 'rf_lca_rear_z': rf_lca_rear_z,
                    'lr_lca_front_x': lr_lca_front_x, 'lr_lca_front_y': lr_lca_front_y, 'lr_lca_front_z': lr_lca_front_z,
                    'lr_lca_rear_x': lr_lca_rear_x, 'lr_lca_rear_y': lr_lca_rear_y, 'lr_lca_rear_z': lr_lca_rear_z,
                    'rr_lca_front_x': rr_lca_front_x, 'rr_lca_front_y': rr_lca_front_y, 'rr_lca_front_z': rr_lca_front_z,
                    'rr_lca_rear_x': rr_lca_rear_x, 'rr_lca_rear_y': rr_lca_rear_y, 'rr_lca_rear_z': rr_lca_rear_z,
                    'lf_y_offset': lf_y_offset, 'rf_y_offset': rf_y_offset,
                    'lr_y_offset': lr_y_offset, 'rr_y_offset': rr_y_offset,
                    'normalize_lca_z': normalize_lca_z
                }
                st.session_state['show_results'] = True

        except Exception as e:
            st.error(f"❌ Error loading file: {str(e)}")
            st.exception(e)

###### MAIN AREA - Results display ######
# Check if we should show results (either button was just clicked OR results were previously calculated)
if uploaded_file is not None and (calculate_button or st.session_state.get('show_results', False)):
    # Helper function to calculate 3D distance
    def calc_distance(x1, y1, z1, x2, y2, z2):
        return np.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    # Restore configuration from session state if not clicking the button (i.e., rerunning due to filter interaction)
    if not calculate_button and 'config' in st.session_state:
        config = st.session_state['config']
        center_section_col = config['center_section_col']
        clip_col = config['clip_col']
        lf_upper_x, lf_upper_y, lf_upper_z = config['lf_upper_x'], config['lf_upper_y'], config['lf_upper_z']
        rf_upper_x, rf_upper_y, rf_upper_z = config['rf_upper_x'], config['rf_upper_y'], config['rf_upper_z']
        lr_upper_x, lr_upper_y, lr_upper_z = config['lr_upper_x'], config['lr_upper_y'], config['lr_upper_z']
        rr_upper_x, rr_upper_y, rr_upper_z = config['rr_upper_x'], config['rr_upper_y'], config['rr_upper_z']
        lf_lca_front_x, lf_lca_front_y, lf_lca_front_z = config['lf_lca_front_x'], config['lf_lca_front_y'], config['lf_lca_front_z']
        lf_lca_rear_x, lf_lca_rear_y, lf_lca_rear_z = config['lf_lca_rear_x'], config['lf_lca_rear_y'], config['lf_lca_rear_z']
        rf_lca_front_x, rf_lca_front_y, rf_lca_front_z = config['rf_lca_front_x'], config['rf_lca_front_y'], config['rf_lca_front_z']
        rf_lca_rear_x, rf_lca_rear_y, rf_lca_rear_z = config['rf_lca_rear_x'], config['rf_lca_rear_y'], config['rf_lca_rear_z']
        lr_lca_front_x, lr_lca_front_y, lr_lca_front_z = config['lr_lca_front_x'], config['lr_lca_front_y'], config['lr_lca_front_z']
        lr_lca_rear_x, lr_lca_rear_y, lr_lca_rear_z = config['lr_lca_rear_x'], config['lr_lca_rear_y'], config['lr_lca_rear_z']
        rr_lca_front_x, rr_lca_front_y, rr_lca_front_z = config['rr_lca_front_x'], config['rr_lca_front_y'], config['rr_lca_front_z']
        rr_lca_rear_x, rr_lca_rear_y, rr_lca_rear_z = config['rr_lca_rear_x'], config['rr_lca_rear_y'], config['rr_lca_rear_z']
        lf_y_offset, rf_y_offset = config['lf_y_offset'], config['rf_y_offset']
        lr_y_offset, rr_y_offset = config['lr_y_offset'], config['rr_y_offset']
        normalize_lca_z = config.get('normalize_lca_z', False)

    # Check if using multi-sheet mode
    using_multi_sheet = st.session_state.get('using_multi_sheet', False)

    # If button was clicked, perform calculations. Otherwise, retrieve from session state.
    if calculate_button:
        if using_multi_sheet:
            # Use separate dataframes for front and rear
            df_front = st.session_state['df_front'].copy()
            df_rear = st.session_state['df_rear'].copy()

            # Calculate LCA center points for all corners
            lf_lca_center_x = (df_front[lf_lca_front_x] + df_front[lf_lca_rear_x]) / 2
            lf_lca_center_y = (df_front[lf_lca_front_y] + df_front[lf_lca_rear_y]) / 2
            lf_lca_center_z = (df_front[lf_lca_front_z] + df_front[lf_lca_rear_z]) / 2

            rf_lca_center_x = (df_front[rf_lca_front_x] + df_front[rf_lca_rear_x]) / 2
            rf_lca_center_y = (df_front[rf_lca_front_y] + df_front[rf_lca_rear_y]) / 2
            rf_lca_center_z = (df_front[rf_lca_front_z] + df_front[rf_lca_rear_z]) / 2

            lr_lca_center_x = (df_rear[lr_lca_front_x] + df_rear[lr_lca_rear_x]) / 2
            lr_lca_center_y = (df_rear[lr_lca_front_y] + df_rear[lr_lca_rear_y]) / 2
            lr_lca_center_z = (df_rear[lr_lca_front_z] + df_rear[lr_lca_rear_z]) / 2

            rr_lca_center_x = (df_rear[rr_lca_front_x] + df_rear[rr_lca_rear_x]) / 2
            rr_lca_center_y = (df_rear[rr_lca_front_y] + df_rear[rr_lca_rear_y]) / 2
            rr_lca_center_z = (df_rear[rr_lca_front_z] + df_rear[rr_lca_rear_z]) / 2

            # Normalize Z heights if requested
            if normalize_lca_z:
                # Combine all Z heights to find global median
                all_z_heights = pd.concat([lf_lca_center_z, rf_lca_center_z, lr_lca_center_z, rr_lca_center_z])
                median_z = all_z_heights.median()

                # Set all Z heights to median
                lf_lca_center_z = pd.Series([median_z] * len(lf_lca_center_z), index=lf_lca_center_z.index)
                rf_lca_center_z = pd.Series([median_z] * len(rf_lca_center_z), index=rf_lca_center_z.index)
                lr_lca_center_z = pd.Series([median_z] * len(lr_lca_center_z), index=lr_lca_center_z.index)
                rr_lca_center_z = pd.Series([median_z] * len(rr_lca_center_z), index=rr_lca_center_z.index)

                st.info(f"✓ LCA Z heights normalized to median: {median_z:.4f}")

            # LF calculations (from front sheet)
            lf_lca_center_x = lf_lca_center_x
            lf_lca_center_y = lf_lca_center_y
            lf_lca_center_z = lf_lca_center_z
            lf_lower_x = lf_lca_center_x
            lf_lower_y = lf_lca_center_y - np.abs(lf_y_offset)
            lf_lower_z = lf_lca_center_z
            df_front['LF_Damper_Length'] = calc_distance(
                df_front[lf_upper_x], df_front[lf_upper_y], df_front[lf_upper_z],
                lf_lower_x, lf_lower_y, lf_lower_z
            )

            # RF calculations (from front sheet)
            rf_lower_x = rf_lca_center_x
            rf_lower_y = rf_lca_center_y + np.abs(rf_y_offset)
            rf_lower_z = rf_lca_center_z
            df_front['RF_Damper_Length'] = calc_distance(
                df_front[rf_upper_x], df_front[rf_upper_y], df_front[rf_upper_z],
                rf_lower_x, rf_lower_y, rf_lower_z
            )

            # LR calculations (from rear sheet)
            # Validate columns exist in rear dataframe
            missing_rear_cols = []
            for col_name, col_var in [('LR LCA Front X', lr_lca_front_x), ('LR LCA Rear X', lr_lca_rear_x),
                                       ('LR LCA Front Y', lr_lca_front_y), ('LR LCA Rear Y', lr_lca_rear_y),
                                       ('LR LCA Front Z', lr_lca_front_z), ('LR LCA Rear Z', lr_lca_rear_z),
                                       ('LR Upper X', lr_upper_x), ('LR Upper Y', lr_upper_y), ('LR Upper Z', lr_upper_z)]:
                if col_var not in df_rear.columns:
                    missing_rear_cols.append(f"{col_name}: '{col_var}'")

            if missing_rear_cols:
                st.error(f"❌ Configuration Error: The following columns selected for LR (Left Rear) don't exist in the Rear sheet:")
                for col in missing_rear_cols:
                    st.error(f"   • {col}")
                st.warning("💡 Please go to the Configuration tab and select columns that exist in your Rear sheet for LR configuration.")
                st.stop()

            lr_lower_x = lr_lca_center_x
            lr_lower_y = lr_lca_center_y - np.abs(lr_y_offset)
            lr_lower_z = lr_lca_center_z
            df_rear['LR_Damper_Length'] = calc_distance(
                df_rear[lr_upper_x], df_rear[lr_upper_y], df_rear[lr_upper_z],
                lr_lower_x, lr_lower_y, lr_lower_z
            )

            # RR calculations (from rear sheet)
            # Validate columns exist in rear dataframe
            missing_rr_cols = []
            for col_name, col_var in [('RR LCA Front X', rr_lca_front_x), ('RR LCA Rear X', rr_lca_rear_x),
                                       ('RR LCA Front Y', rr_lca_front_y), ('RR LCA Rear Y', rr_lca_rear_y),
                                       ('RR LCA Front Z', rr_lca_front_z), ('RR LCA Rear Z', rr_lca_rear_z),
                                       ('RR Upper X', rr_upper_x), ('RR Upper Y', rr_upper_y), ('RR Upper Z', rr_upper_z)]:
                if col_var not in df_rear.columns:
                    missing_rr_cols.append(f"{col_name}: '{col_var}'")

            if missing_rr_cols:
                st.error(f"❌ Configuration Error: The following columns selected for RR (Right Rear) don't exist in the Rear sheet:")
                for col in missing_rr_cols:
                    st.error(f"   • {col}")
                st.warning("💡 Please go to the Configuration tab and select columns that exist in your Rear sheet for RR configuration.")
                st.stop()

            rr_lower_x = rr_lca_center_x
            rr_lower_y = rr_lca_center_y + np.abs(rr_y_offset)
            rr_lower_z = rr_lca_center_z
            df_rear['RR_Damper_Length'] = calc_distance(
                df_rear[rr_upper_x], df_rear[rr_upper_y], df_rear[rr_upper_z],
                rr_lower_x, rr_lower_y, rr_lower_z
            )

            # Store the calculated dataframes back to session state for display tabs
            st.session_state['df_front_calc'] = df_front.copy()
            st.session_state['df_rear_calc'] = df_rear.copy()

            # Merge front and rear results
            # Create all combinations: each front clip can work with each rear clip for a given center section
            # Add suffix to distinguish front vs rear clip columns
            df_front_renamed = df_front[[center_section_col, clip_col, 'LF_Damper_Length', 'RF_Damper_Length']].copy()
            df_front_renamed.rename(columns={clip_col: 'Front_Clip'}, inplace=True)

            df_rear_renamed = df_rear[[center_section_col, clip_col, 'LR_Damper_Length', 'RR_Damper_Length']].copy()
            df_rear_renamed.rename(columns={clip_col: 'Rear_Clip'}, inplace=True)

            # Merge on center section only - creates all combinations of front and rear clips
            results_df = pd.merge(
                df_front_renamed,
                df_rear_renamed,
                on=[center_section_col],
                how='inner'
            )

            # Check if merge resulted in empty dataframe
            if len(results_df) == 0:
                st.error("❌ No matching Center Sections found between front and rear sheets!")
                st.info("Make sure both sheets have the same Center Section values.")
                st.stop()

            # Create a combined clip column for display
            results_df['Clip_Combination'] = results_df['Front_Clip'] + ' / ' + results_df['Rear_Clip']

            # Update clip_col reference to use the combination column for grouping
            clip_col_display = 'Clip_Combination'

        else:
            # Single sheet mode - use df for all calculations
            results_df = df.copy()

            # LF calculations
            lf_lca_center_x = (results_df[lf_lca_front_x] + results_df[lf_lca_rear_x]) / 2
            lf_lca_center_y = (results_df[lf_lca_front_y] + results_df[lf_lca_rear_y]) / 2
            lf_lca_center_z = (results_df[lf_lca_front_z] + results_df[lf_lca_rear_z]) / 2
            lf_lower_x = lf_lca_center_x
            lf_lower_y = lf_lca_center_y - np.abs(lf_y_offset)
            lf_lower_z = lf_lca_center_z
            results_df['LF_Damper_Length'] = calc_distance(
                results_df[lf_upper_x], results_df[lf_upper_y], results_df[lf_upper_z],
                lf_lower_x, lf_lower_y, lf_lower_z
            )

            # RF calculations
            rf_lca_center_x = (results_df[rf_lca_front_x] + results_df[rf_lca_rear_x]) / 2
            rf_lca_center_y = (results_df[rf_lca_front_y] + results_df[rf_lca_rear_y]) / 2
            rf_lca_center_z = (results_df[rf_lca_front_z] + results_df[rf_lca_rear_z]) / 2
            rf_lower_x = rf_lca_center_x
            rf_lower_y = rf_lca_center_y + np.abs(rf_y_offset)
            rf_lower_z = rf_lca_center_z
            results_df['RF_Damper_Length'] = calc_distance(
                results_df[rf_upper_x], results_df[rf_upper_y], results_df[rf_upper_z],
                rf_lower_x, rf_lower_y, rf_lower_z
            )

            # LR calculations
            lr_lca_center_x = (results_df[lr_lca_front_x] + results_df[lr_lca_rear_x]) / 2
            lr_lca_center_y = (results_df[lr_lca_front_y] + results_df[lr_lca_rear_y]) / 2
            lr_lca_center_z = (results_df[lr_lca_front_z] + results_df[lr_lca_rear_z]) / 2
            lr_lower_x = lr_lca_center_x
            lr_lower_y = lr_lca_center_y - np.abs(lr_y_offset)
            lr_lower_z = lr_lca_center_z
            results_df['LR_Damper_Length'] = calc_distance(
                results_df[lr_upper_x], results_df[lr_upper_y], results_df[lr_upper_z],
                lr_lower_x, lr_lower_y, lr_lower_z
            )

            # RR calculations
            rr_lca_center_x = (results_df[rr_lca_front_x] + results_df[rr_lca_rear_x]) / 2
            rr_lca_center_y = (results_df[rr_lca_front_y] + results_df[rr_lca_rear_y]) / 2
            rr_lca_center_z = (results_df[rr_lca_front_z] + results_df[rr_lca_rear_z]) / 2
            rr_lower_x = rr_lca_center_x
            rr_lower_y = rr_lca_center_y + np.abs(rr_y_offset)
            rr_lower_z = rr_lca_center_z
            results_df['RR_Damper_Length'] = calc_distance(
                results_df[rr_upper_x], results_df[rr_upper_y], results_df[rr_upper_z],
                rr_lower_x, rr_lower_y, rr_lower_z
            )

        # Drop any rows with missing damper length values
        results_df = results_df.dropna(subset=['LF_Damper_Length', 'RF_Damper_Length', 'LR_Damper_Length', 'RR_Damper_Length'])

        # Calculate individual corner rankings (higher damper length = better = rank 1)
        results_df['LF_Rank'] = results_df['LF_Damper_Length'].rank(ascending=False, method='min').astype(int)
        results_df['RF_Rank'] = results_df['RF_Damper_Length'].rank(ascending=False, method='min').astype(int)
        results_df['LR_Rank'] = results_df['LR_Damper_Length'].rank(ascending=False, method='min').astype(int)
        results_df['RR_Rank'] = results_df['RR_Damper_Length'].rank(ascending=False, method='min').astype(int)

        # Calculate weighted front rank (LF is 2x more important than RF)
        # Lower score is better
        results_df['Front_Weighted_Score'] = (results_df['LF_Rank'] * 2) + (results_df['RF_Rank'] * 1)
        results_df['Front_Rank'] = results_df['Front_Weighted_Score'].rank(method='min').astype(int)

        # Overall rank based on LF (most important for front)
        results_df = results_df.sort_values('LF_Damper_Length', ascending=False).reset_index(drop=True)

        # Store results in session state for persistence across reruns
        st.session_state['results_df'] = results_df
        st.success("✅ Calculations complete! Switch to the 'Analysis' tab to view results.")

# Analysis Tab
with analysis_tab:
    # Check if results exist
    if 'results_df' in st.session_state:
        results_df = st.session_state['results_df']
        using_multi_sheet = st.session_state.get('using_multi_sheet', False)

        # Get column names from session state
        center_section_col = st.session_state.get('center_section_col', 'Center_Section')
        clip_col = st.session_state.get('clip_col', 'Clip')

        # Main tabs - Reports vs Visualizer
        reports_tab, visualizer_tab = st.tabs([
            "📊 Reports & Tables",
            "🎯 3D Assembly Visualizer"
        ])

        with reports_tab:
            # Sub-tabs for different reports
            front_results_tab, rear_results_tab, center_summary_tab, clip_summary_tab, scatter_tab, attribute_tab, selector_tab = st.tabs([
            "🔵 Front Clip Results",
            "🟢 Rear Clip Results",
            "📊 Center Section Rankings",
            "📊 Clip Rankings",
            "📈 Scatter Analysis",
            "🔬 Attribute Compare",
            "🎯 Selector"
        ])

        with front_results_tab:
            st.subheader("Front Clip Combinations (LF/RF)")

            if using_multi_sheet:
                # For multi-sheet, get unique front clip + center combinations from front sheet
                df_front_display = st.session_state['df_front_calc'][[center_section_col, clip_col, 'LF_Damper_Length', 'RF_Damper_Length']].copy()
                df_front_display.rename(columns={clip_col: 'Front_Clip'}, inplace=True)

                # Calculate ranks for front only
                df_front_display['LF_Rank'] = df_front_display['LF_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_front_display['RF_Rank'] = df_front_display['RF_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_front_display['Front_Weighted_Score'] = (df_front_display['LF_Rank'] * 2) + (df_front_display['RF_Rank'] * 1)
                df_front_display['Front_Rank'] = df_front_display['Front_Weighted_Score'].rank(method='min').astype(int)

                front_display_cols = [center_section_col, 'Front_Clip',
                                     'LF_Damper_Length', 'LF_Rank',
                                     'RF_Damper_Length', 'RF_Rank',
                                     'Front_Rank']
                front_df = df_front_display[front_display_cols].copy()
            else:
                front_display_cols = [center_section_col, clip_col,
                                     'LF_Damper_Length', 'LF_Rank',
                                     'RF_Damper_Length', 'RF_Rank',
                                     'Front_Rank']
                front_df = results_df[front_display_cols].copy()

            # Round the length columns
            for col in ['LF_Damper_Length', 'RF_Damper_Length']:
                front_df[col] = front_df[col].round(3)

            # Add filter controls
            with st.expander("🔍 Filter Front Results", expanded=False):
                if using_multi_sheet:
                    filter_cols = st.columns(3)
                    with filter_cols[0]:
                        center_filter = st.multiselect(
                            "Filter by Center Section",
                            options=sorted(front_df[center_section_col].unique()),
                            default=None,
                            key='front_center_filter'
                        )
                    with filter_cols[1]:
                        front_clip_filter = st.multiselect(
                            "Filter by Front Clip",
                            options=sorted(front_df['Front_Clip'].unique()),
                            default=None,
                            key='front_clip_filter'
                        )
                    with filter_cols[2]:
                        max_rank = int(front_df['Front_Rank'].max())
                        if max_rank > 1:
                            rank_filter = st.slider(
                                "Max Front Rank",
                                min_value=1,
                                max_value=max_rank,
                                value=max_rank,
                                key='front_rank_filter'
                            )
                        else:
                            rank_filter = max_rank
                            st.info("Only one rank available")

                    # Apply filters
                    if center_filter:
                        front_df = front_df[front_df[center_section_col].isin(center_filter)]
                    if front_clip_filter:
                        front_df = front_df[front_df['Front_Clip'].isin(front_clip_filter)]
                    front_df = front_df[front_df['Front_Rank'] <= rank_filter]
                else:
                    filter_cols = st.columns(3)
                    with filter_cols[0]:
                        center_filter = st.multiselect(
                            "Filter by Center Section",
                            options=sorted(front_df[center_section_col].unique()),
                            default=None,
                            key='front_center_filter'
                        )
                    with filter_cols[1]:
                        clip_filter = st.multiselect(
                            "Filter by Clip",
                            options=sorted(front_df[clip_col].unique()),
                            default=None,
                            key='front_clip_filter'
                        )
                    with filter_cols[2]:
                        max_rank = int(front_df['Front_Rank'].max())
                        if max_rank > 1:
                            rank_filter = st.slider(
                                "Max Front Rank",
                                min_value=1,
                                max_value=max_rank,
                                value=max_rank,
                                key='front_rank_filter'
                            )
                        else:
                            rank_filter = max_rank
                            st.info("Only one rank available")

                    # Apply filters
                    if center_filter:
                        front_df = front_df[front_df[center_section_col].isin(center_filter)]
                    if clip_filter:
                        front_df = front_df[front_df[clip_col].isin(clip_filter)]
                    front_df = front_df[front_df['Front_Rank'] <= rank_filter]

            st.dataframe(
                front_df,
                use_container_width=True,
                height=600,
                hide_index=True,
                column_config={
                    "LF_Damper_Length": st.column_config.ProgressColumn(
                        "LF Length",
                        help="Left Front Damper Length",
                        format="%.3f",
                        min_value=front_df['LF_Damper_Length'].min(),
                        max_value=front_df['LF_Damper_Length'].max(),
                    ),
                    "RF_Damper_Length": st.column_config.ProgressColumn(
                        "RF Length",
                        help="Right Front Damper Length",
                        format="%.3f",
                        min_value=front_df['RF_Damper_Length'].min(),
                        max_value=front_df['RF_Damper_Length'].max(),
                    ),
                }
            )

        with rear_results_tab:
            st.subheader("Rear Clip Combinations (LR/RR)")

            if using_multi_sheet:
                # For multi-sheet, get unique rear clip + center combinations from rear sheet
                df_rear_display = st.session_state['df_rear_calc'][[center_section_col, clip_col, 'LR_Damper_Length', 'RR_Damper_Length']].copy()
                df_rear_display.rename(columns={clip_col: 'Rear_Clip'}, inplace=True)

                # Calculate ranks for rear only
                df_rear_display['LR_Rank'] = df_rear_display['LR_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_rear_display['RR_Rank'] = df_rear_display['RR_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_rear_display['Rear_Weighted_Score'] = (df_rear_display['LR_Rank'] * 2) + (df_rear_display['RR_Rank'] * 1)
                df_rear_display['Rear_Rank'] = df_rear_display['Rear_Weighted_Score'].rank(method='min').astype(int)

                rear_display_cols = [center_section_col, 'Rear_Clip',
                                    'LR_Damper_Length', 'LR_Rank',
                                    'RR_Damper_Length', 'RR_Rank',
                                    'Rear_Rank']
                rear_df = df_rear_display[rear_display_cols].copy()
            else:
                rear_display_cols = [center_section_col, clip_col,
                                    'LR_Damper_Length', 'LR_Rank',
                                    'RR_Damper_Length', 'RR_Rank']
                rear_df = results_df[rear_display_cols].copy()

            # Sort by LR for rear
            rear_df = rear_df.sort_values('LR_Damper_Length', ascending=False).reset_index(drop=True)

            # Round the length columns
            for col in ['LR_Damper_Length', 'RR_Damper_Length']:
                rear_df[col] = rear_df[col].round(3)

            # Add filter controls
            with st.expander("🔍 Filter Rear Results", expanded=False):
                if using_multi_sheet:
                    filter_cols = st.columns(3)
                    with filter_cols[0]:
                        center_filter_rear = st.multiselect(
                            "Filter by Center Section",
                            options=sorted(rear_df[center_section_col].unique()),
                            default=None,
                            key='rear_center_filter'
                        )
                    with filter_cols[1]:
                        rear_clip_filter_rear = st.multiselect(
                            "Filter by Rear Clip",
                            options=sorted(rear_df['Rear_Clip'].unique()),
                            default=None,
                            key='rear_clip_filter'
                        )
                    with filter_cols[2]:
                        max_rank_rear = int(rear_df['LR_Rank'].max())
                        if max_rank_rear > 1:
                            rank_filter_rear = st.slider(
                                "Max LR Rank",
                                min_value=1,
                                max_value=max_rank_rear,
                                value=max_rank_rear,
                                key='rear_rank_filter'
                            )
                        else:
                            rank_filter_rear = max_rank_rear
                            st.info("Only one rank available")

                    # Apply filters
                    if center_filter_rear:
                        rear_df = rear_df[rear_df[center_section_col].isin(center_filter_rear)]
                    if rear_clip_filter_rear:
                        rear_df = rear_df[rear_df['Rear_Clip'].isin(rear_clip_filter_rear)]
                    rear_df = rear_df[rear_df['LR_Rank'] <= rank_filter_rear]
                else:
                    filter_cols = st.columns(3)
                    with filter_cols[0]:
                        center_filter_rear = st.multiselect(
                            "Filter by Center Section",
                            options=sorted(rear_df[center_section_col].unique()),
                            default=None,
                            key='rear_center_filter'
                        )
                    with filter_cols[1]:
                        clip_filter_rear = st.multiselect(
                            "Filter by Clip",
                            options=sorted(rear_df[clip_col].unique()),
                            default=None,
                            key='rear_clip_filter'
                        )
                    with filter_cols[2]:
                        max_rank_rear = int(rear_df['LR_Rank'].max())
                        if max_rank_rear > 1:
                            rank_filter_rear = st.slider(
                                "Max LR Rank",
                                min_value=1,
                                max_value=max_rank_rear,
                                value=max_rank_rear,
                                key='rear_rank_filter'
                            )
                        else:
                            rank_filter_rear = max_rank_rear
                            st.info("Only one rank available")

                    # Apply filters
                    if center_filter_rear:
                        rear_df = rear_df[rear_df[center_section_col].isin(center_filter_rear)]
                    if clip_filter_rear:
                        rear_df = rear_df[rear_df[clip_col].isin(clip_filter_rear)]
                    rear_df = rear_df[rear_df['LR_Rank'] <= rank_filter_rear]

            st.dataframe(
                rear_df,
                use_container_width=True,
                height=600,
                hide_index=True,
                column_config={
                    "LR_Damper_Length": st.column_config.ProgressColumn(
                        "LR Length",
                        help="Left Rear Damper Length",
                        format="%.3f",
                        min_value=rear_df['LR_Damper_Length'].min(),
                        max_value=rear_df['LR_Damper_Length'].max(),
                    ),
                    "RR_Damper_Length": st.column_config.ProgressColumn(
                        "RR Length",
                        help="Right Rear Damper Length",
                        format="%.3f",
                        min_value=rear_df['RR_Damper_Length'].min(),
                        max_value=rear_df['RR_Damper_Length'].max(),
                    ),
                }
            )

        with center_summary_tab:
            st.subheader("Center Section Performance Rankings")
            st.markdown("*Average rankings across all clip combinations*")

            # Group by center section and calculate averages
            if using_multi_sheet:
                # For multi-sheet, calculate front and rear rankings separately then combine
                df_front_calc_ranks = st.session_state['df_front_calc'].copy()
                df_rear_calc_ranks = st.session_state['df_rear_calc'].copy()

                # Calculate ranks within each dataframe
                df_front_calc_ranks['LF_Rank'] = df_front_calc_ranks['LF_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_front_calc_ranks['RF_Rank'] = df_front_calc_ranks['RF_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_front_calc_ranks['Front_Weighted_Score'] = (df_front_calc_ranks['LF_Rank'] * 2) + (df_front_calc_ranks['RF_Rank'] * 1)
                df_front_calc_ranks['Front_Rank'] = df_front_calc_ranks['Front_Weighted_Score'].rank(method='min').astype(int)

                df_rear_calc_ranks['LR_Rank'] = df_rear_calc_ranks['LR_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_rear_calc_ranks['RR_Rank'] = df_rear_calc_ranks['RR_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_rear_calc_ranks['Rear_Weighted_Score'] = (df_rear_calc_ranks['LR_Rank'] * 2) + (df_rear_calc_ranks['RR_Rank'] * 1)
                df_rear_calc_ranks['Rear_Rank'] = df_rear_calc_ranks['Rear_Weighted_Score'].rank(method='min').astype(int)

                # Group by center section for front data
                front_center_agg = df_front_calc_ranks.groupby(center_section_col).agg({
                    'LF_Rank': 'mean',
                    'RF_Rank': 'mean',
                    'Front_Rank': 'mean',
                    'LF_Damper_Length': 'mean',
                    'RF_Damper_Length': 'mean'
                }).reset_index()

                # Group by center section for rear data
                rear_center_agg = df_rear_calc_ranks.groupby(center_section_col).agg({
                    'LR_Rank': 'mean',
                    'RR_Rank': 'mean',
                    'Rear_Rank': 'mean',
                    'LR_Damper_Length': 'mean',
                    'RR_Damper_Length': 'mean'
                }).reset_index()

                # Merge front and rear aggregations
                center_rankings = pd.merge(
                    front_center_agg,
                    rear_center_agg,
                    on=center_section_col,
                    how='outer'
                )
            else:
                center_rankings = results_df.groupby(center_section_col).agg({
                    'LF_Rank': 'mean',
                    'RF_Rank': 'mean',
                    'LR_Rank': 'mean',
                    'RR_Rank': 'mean',
                    'Front_Rank': 'mean',
                    'LF_Damper_Length': 'mean',
                    'RF_Damper_Length': 'mean',
                    'LR_Damper_Length': 'mean',
                    'RR_Damper_Length': 'mean'
                }).reset_index()
                center_rankings['Rear_Rank'] = (center_rankings['LR_Rank'] + center_rankings['RR_Rank']) / 2

            # Sort by front rank
            center_rankings = center_rankings.sort_values('Front_Rank').reset_index(drop=True)

            # Round values (don't round damper lengths - let format handle display)
            for col in center_rankings.columns:
                if col != center_section_col:
                    if 'Damper_Length' not in col:
                        center_rankings[col] = center_rankings[col].round(2)

            st.dataframe(
                center_rankings,
                use_container_width=True,
                height=400,
                hide_index=True,
                column_config={
                    center_section_col: "Center Section",
                    "LF_Rank": "Avg LF Rank",
                    "RF_Rank": "Avg RF Rank",
                    "LR_Rank": "Avg LR Rank",
                    "RR_Rank": "Avg RR Rank",
                    "Front_Rank": "Avg Front Rank",
                    "Rear_Rank": "Avg Rear Rank",
                    "LF_Damper_Length": st.column_config.ProgressColumn(
                        "Avg LF Length",
                        help="Average LF Damper Length",
                        format="%.4f",
                        min_value=center_rankings['LF_Damper_Length'].min(),
                        max_value=center_rankings['LF_Damper_Length'].max(),
                    ),
                    "RF_Damper_Length": st.column_config.ProgressColumn(
                        "Avg RF Length",
                        help="Average RF Damper Length",
                        format="%.4f",
                        min_value=center_rankings['RF_Damper_Length'].min(),
                        max_value=center_rankings['RF_Damper_Length'].max(),
                    ),
                    "LR_Damper_Length": st.column_config.ProgressColumn(
                        "Avg LR Length",
                        help="Average LR Damper Length",
                        format="%.4f",
                        min_value=center_rankings['LR_Damper_Length'].min(),
                        max_value=center_rankings['LR_Damper_Length'].max(),
                    ),
                    "RR_Damper_Length": st.column_config.ProgressColumn(
                        "Avg RR Length",
                        help="Average RR Damper Length",
                        format="%.4f",
                        min_value=center_rankings['RR_Damper_Length'].min(),
                        max_value=center_rankings['RR_Damper_Length'].max(),
                    ),
                }
            )

        with clip_summary_tab:
            st.subheader("Clip Performance Rankings")
            st.markdown("*Average rankings across all center section combinations*")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Front Clips (LF/RF)**")
                # Group by clip for front
                if using_multi_sheet:
                    # Use df_front_calc_ranks instead of results_df to get correct rankings
                    front_clip_rankings = df_front_calc_ranks.groupby(clip_col).agg({
                        'LF_Rank': 'mean',
                        'RF_Rank': 'mean',
                        'Front_Rank': 'mean',
                        'LF_Damper_Length': 'mean',
                        'RF_Damper_Length': 'mean'
                    }).reset_index()
                    front_clip_rankings.rename(columns={clip_col: 'Front_Clip'}, inplace=True)
                    clip_display_col = 'Front_Clip'
                else:
                    front_clip_rankings = results_df.groupby(clip_col).agg({
                        'LF_Rank': 'mean',
                        'RF_Rank': 'mean',
                        'Front_Rank': 'mean',
                        'LF_Damper_Length': 'mean',
                        'RF_Damper_Length': 'mean'
                    }).reset_index()
                    clip_display_col = clip_col

                front_clip_rankings = front_clip_rankings.sort_values('Front_Rank').reset_index(drop=True)

                for col in front_clip_rankings.columns:
                    if col != clip_display_col:
                        if 'Damper_Length' not in col:
                            front_clip_rankings[col] = front_clip_rankings[col].round(2)

                st.dataframe(
                    front_clip_rankings,
                    use_container_width=True,
                    height=400,
                    hide_index=True,
                    column_config={
                        clip_display_col: "Front Clip",
                        "LF_Rank": "Avg LF Rank",
                        "RF_Rank": "Avg RF Rank",
                        "Front_Rank": "Avg Front Rank",
                        "LF_Damper_Length": st.column_config.ProgressColumn(
                            "Avg LF Length",
                            help="Average LF Damper Length",
                            format="%.4f",
                            min_value=front_clip_rankings['LF_Damper_Length'].min(),
                            max_value=front_clip_rankings['LF_Damper_Length'].max(),
                        ),
                        "RF_Damper_Length": st.column_config.ProgressColumn(
                            "Avg RF Length",
                            help="Average RF Damper Length",
                            format="%.4f",
                            min_value=front_clip_rankings['RF_Damper_Length'].min(),
                            max_value=front_clip_rankings['RF_Damper_Length'].max(),
                        ),
                    }
                )

            with col2:
                st.markdown("**Rear Clips (LR/RR)**")
                # Group by clip for rear
                if using_multi_sheet:
                    # Use df_rear_calc_ranks instead of results_df to get correct rankings
                    rear_clip_rankings = df_rear_calc_ranks.groupby(clip_col).agg({
                        'LR_Rank': 'mean',
                        'RR_Rank': 'mean',
                        'Rear_Rank': 'mean',
                        'LR_Damper_Length': 'mean',
                        'RR_Damper_Length': 'mean'
                    }).reset_index()
                    rear_clip_rankings.rename(columns={clip_col: 'Rear_Clip'}, inplace=True)
                    rear_clip_display_col = 'Rear_Clip'
                else:
                    rear_clip_rankings = results_df.groupby(clip_col).agg({
                        'LR_Rank': 'mean',
                        'RR_Rank': 'mean',
                        'LR_Damper_Length': 'mean',
                        'RR_Damper_Length': 'mean'
                    }).reset_index()
                    rear_clip_display_col = clip_col
                    # Calculate rear rank for single-sheet mode
                    rear_clip_rankings['Rear_Rank'] = (rear_clip_rankings['LR_Rank'] + rear_clip_rankings['RR_Rank']) / 2

                # Sort by Rear_Rank
                rear_clip_rankings = rear_clip_rankings.sort_values('Rear_Rank').reset_index(drop=True)

                for col in rear_clip_rankings.columns:
                    if col != rear_clip_display_col:
                        if 'Damper_Length' not in col:
                            rear_clip_rankings[col] = rear_clip_rankings[col].round(2)

                st.dataframe(
                    rear_clip_rankings,
                    use_container_width=True,
                    height=400,
                    hide_index=True,
                    column_config={
                        rear_clip_display_col: "Rear Clip",
                        "LR_Rank": "Avg LR Rank",
                        "RR_Rank": "Avg RR Rank",
                        "Rear_Rank": "Avg Rear Rank",
                        "LR_Damper_Length": st.column_config.ProgressColumn(
                            "Avg LR Length",
                            help="Average LR Damper Length",
                            format="%.4f",
                            min_value=rear_clip_rankings['LR_Damper_Length'].min(),
                            max_value=rear_clip_rankings['LR_Damper_Length'].max(),
                        ),
                        "RR_Damper_Length": st.column_config.ProgressColumn(
                            "Avg RR Length",
                            help="Average RR Damper Length",
                            format="%.4f",
                            min_value=rear_clip_rankings['RR_Damper_Length'].min(),
                            max_value=rear_clip_rankings['RR_Damper_Length'].max(),
                        ),
                    }
                )

        with scatter_tab:

            # View mode toggle and filters
            control_cols = st.columns([1.5, 2, 1.5])
            with control_cols[0]:
                view_mode = st.radio(
                    "View Mode:",
                    options=["Center Section View", "Clip View"],
                    key='scatter_view_mode',
                    horizontal=True,
                    help="Center Section View: Colors by center section\nClip View: Colors by clip, shapes by center section"
                )

            # Prepare data for filtering
            if using_multi_sheet:
                front_data_all = st.session_state['df_front_calc'][[
                    center_section_col, clip_col, 'LF_Damper_Length', 'RF_Damper_Length'
                ]].copy()
                front_data_all.rename(columns={clip_col: 'Front_Clip'}, inplace=True)

                rear_data_all = st.session_state['df_rear_calc'][[
                    center_section_col, clip_col, 'LR_Damper_Length', 'RR_Damper_Length'
                ]].copy()
                rear_data_all.rename(columns={clip_col: 'Rear_Clip'}, inplace=True)
            else:
                front_data_all = results_df[[
                    center_section_col, clip_col, 'LF_Damper_Length', 'RF_Damper_Length'
                ]].copy()

                rear_data_all = results_df[[
                    center_section_col, clip_col, 'LR_Damper_Length', 'RR_Damper_Length'
                ]].copy()

            # Get unique values for filters
            all_center_sections = sorted(front_data_all[center_section_col].unique())
            if using_multi_sheet:
                all_front_clips = sorted(front_data_all['Front_Clip'].unique())
                all_rear_clips = sorted(rear_data_all['Rear_Clip'].unique())
            else:
                all_clips = sorted(front_data_all[clip_col].unique())

            # Show appropriate filters based on view mode
            if view_mode == "Clip View":
                with control_cols[1]:
                    st.markdown("**Filter Center Sections:**")
                    selected_centers = st.multiselect(
                        "Select Center Sections",
                        options=all_center_sections,
                        default=all_center_sections[:3] if len(all_center_sections) > 3 else all_center_sections,
                        key='scatter_center_filter',
                        help="Select which center sections to display"
                    )
                with control_cols[2]:
                    st.markdown("**Info:**")
                    st.caption("🔵 Clips are colored, center sections use different shapes")
            else:
                # Center Section View - add clip filter with toggles
                # Initialize clip visibility in session state
                if 'visible_front_clips' not in st.session_state:
                    st.session_state['visible_front_clips'] = set(all_front_clips if using_multi_sheet else all_clips)
                if 'visible_rear_clips' not in st.session_state and using_multi_sheet:
                    st.session_state['visible_rear_clips'] = set(all_rear_clips)

                with control_cols[1]:
                    if using_multi_sheet:
                        with st.expander("Front Clips", expanded=False):
                            # Create columns for compact layout
                            num_clips = len(all_front_clips)
                            num_cols = min(3, num_clips)
                            clip_cols = st.columns(num_cols)

                            for idx, clip in enumerate(all_front_clips):
                                col_idx = idx % num_cols
                                with clip_cols[col_idx]:
                                    is_visible = clip in st.session_state['visible_front_clips']
                                    toggled = st.checkbox(clip, value=is_visible, key=f'front_clip_toggle_{clip}')
                                    if toggled and clip not in st.session_state['visible_front_clips']:
                                        st.session_state['visible_front_clips'].add(clip)
                                    elif not toggled and clip in st.session_state['visible_front_clips']:
                                        st.session_state['visible_front_clips'].discard(clip)
                    else:
                        with st.expander("Clips", expanded=False):
                            num_clips = len(all_clips)
                            num_cols = min(3, num_clips)
                            clip_cols = st.columns(num_cols)

                            for idx, clip in enumerate(all_clips):
                                col_idx = idx % num_cols
                                with clip_cols[col_idx]:
                                    is_visible = clip in st.session_state['visible_front_clips']
                                    toggled = st.checkbox(clip, value=is_visible, key=f'clip_toggle_{clip}')
                                    if toggled and clip not in st.session_state['visible_front_clips']:
                                        st.session_state['visible_front_clips'].add(clip)
                                    elif not toggled and clip in st.session_state['visible_front_clips']:
                                        st.session_state['visible_front_clips'].discard(clip)

                with control_cols[2]:
                    if using_multi_sheet:
                        with st.expander("Rear Clips", expanded=False):
                            num_clips = len(all_rear_clips)
                            num_cols = min(3, num_clips)
                            clip_cols = st.columns(num_cols)

                            for idx, clip in enumerate(all_rear_clips):
                                col_idx = idx % num_cols
                                with clip_cols[col_idx]:
                                    is_visible = clip in st.session_state['visible_rear_clips']
                                    toggled = st.checkbox(clip, value=is_visible, key=f'rear_clip_toggle_{clip}')
                                    if toggled and clip not in st.session_state['visible_rear_clips']:
                                        st.session_state['visible_rear_clips'].add(clip)
                                    elif not toggled and clip in st.session_state['visible_rear_clips']:
                                        st.session_state['visible_rear_clips'].discard(clip)
                    else:
                        st.markdown("")

                # Convert to exclude lists for compatibility with existing code
                if using_multi_sheet:
                    exclude_front_clips = [c for c in all_front_clips if c not in st.session_state['visible_front_clips']]
                    exclude_rear_clips = [c for c in all_rear_clips if c not in st.session_state['visible_rear_clips']]
                else:
                    exclude_clips = [c for c in all_clips if c not in st.session_state['visible_front_clips']]

            # Create two columns for front and rear scatter plots
            scatter_col1, scatter_col2 = st.columns(2)

            with scatter_col1:
                st.markdown("<p style='margin-bottom: 0.5rem;'><strong>LF vs RF Damper Length</strong></p>", unsafe_allow_html=True)

                # Create scatter plot
                fig_front = go.Figure()
                colors = px.colors.qualitative.Plotly
                marker_symbols = ['circle', 'square', 'diamond', 'cross', 'x', 'triangle-up', 'triangle-down', 'star']

                if view_mode == "Center Section View":
                    # Original view: Color by center section
                    scatter_data = front_data_all.copy()
                    clip_col_name = 'Front_Clip' if using_multi_sheet else clip_col

                    # Apply clip filter
                    if using_multi_sheet:
                        if exclude_front_clips:
                            scatter_data = scatter_data[~scatter_data[clip_col_name].isin(exclude_front_clips)]
                    else:
                        if exclude_clips:
                            scatter_data = scatter_data[~scatter_data[clip_col_name].isin(exclude_clips)]

                    center_sections = scatter_data[center_section_col].unique()

                    for idx, center in enumerate(sorted(center_sections)):
                        center_data = scatter_data[scatter_data[center_section_col] == center]

                        fig_front.add_trace(go.Scatter(
                            x=center_data['LF_Damper_Length'].tolist(),
                            y=center_data['RF_Damper_Length'].tolist(),
                            mode='markers',
                            name=str(center),
                            marker=dict(
                                size=12,
                                color=colors[idx % len(colors)],
                                line=dict(width=1, color='white')
                            ),
                            text=center_data[clip_col_name].tolist(),
                            hovertemplate='<b>Center Section:</b> %{fullData.name}<br>' +
                                        f'<b>{clip_col_name}:</b> %{{text}}<br>' +
                                        '<b>LF Length:</b> %{x:.4f}<br>' +
                                        '<b>RF Length:</b> %{y:.4f}<br>' +
                                        '<extra></extra>'
                        ))

                    legend_title = "Center Section"

                else:
                    # Clip View: Color by clip, shape by center section
                    if view_mode == "Clip View" and not selected_centers:
                        st.warning("Please select at least one center section to display")
                    else:
                        scatter_data = front_data_all[front_data_all[center_section_col].isin(selected_centers)].copy()
                        clip_col_name = 'Front_Clip' if using_multi_sheet else clip_col
                        unique_clips = sorted(scatter_data[clip_col_name].unique())
                        selected_centers_sorted = sorted(selected_centers)

                        for center_idx, center in enumerate(selected_centers_sorted):
                            for clip_idx, clip in enumerate(unique_clips):
                                clip_center_data = scatter_data[
                                    (scatter_data[center_section_col] == center) &
                                    (scatter_data[clip_col_name] == clip)
                                ]

                                if len(clip_center_data) > 0:
                                    fig_front.add_trace(go.Scatter(
                                        x=clip_center_data['LF_Damper_Length'].tolist(),
                                        y=clip_center_data['RF_Damper_Length'].tolist(),
                                        mode='markers',
                                        name=f"{clip}",
                                        legendgroup=clip,
                                        marker=dict(
                                            size=14,
                                            color=colors[clip_idx % len(colors)],
                                            symbol=marker_symbols[center_idx % len(marker_symbols)],
                                            line=dict(width=1, color='white')
                                        ),
                                        text=[f"Center: {center}"] * len(clip_center_data),
                                        hovertemplate=f'<b>{clip_col_name}:</b> {clip}<br>' +
                                                    '<b>Center Section:</b> %{text}<br>' +
                                                    '<b>LF Length:</b> %{x:.4f}<br>' +
                                                    '<b>RF Length:</b> %{y:.4f}<br>' +
                                                    '<extra></extra>',
                                        showlegend=(center_idx == 0)  # Only show legend for first center section
                                    ))

                        legend_title = f"Clip (Shapes: {', '.join(selected_centers_sorted)})"

                # Update layout for front plot
                fig_front.update_layout(
                    xaxis_title="LF Damper Length",
                    yaxis_title="RF Damper Length",
                    hovermode='closest',
                    legend=dict(
                        title=legend_title,
                        yanchor="top",
                        y=0.99,
                        xanchor="right",
                        x=0.99
                    ),
                    height=600,
                    xaxis=dict(tickformat='.3f'),
                    yaxis=dict(tickformat='.3f')
                )

                st.plotly_chart(fig_front, use_container_width=True)

                # Add insights
                if using_multi_sheet:
                    corr = scatter_data['LF_Damper_Length'].corr(scatter_data['RF_Damper_Length'])
                    st.metric("LF-RF Correlation", f"{corr:.3f}")

            with scatter_col2:
                st.markdown("<p style='margin-bottom: 0.5rem;'><strong>LR vs RR Damper Length</strong></p>", unsafe_allow_html=True)

                # Create scatter plot
                fig_rear = go.Figure()

                if view_mode == "Center Section View":
                    # Original view: Color by center section
                    scatter_data_rear = rear_data_all.copy()
                    clip_col_name_rear = 'Rear_Clip' if using_multi_sheet else clip_col

                    # Apply clip filter
                    if using_multi_sheet:
                        if exclude_rear_clips:
                            scatter_data_rear = scatter_data_rear[~scatter_data_rear[clip_col_name_rear].isin(exclude_rear_clips)]
                    else:
                        if exclude_clips:
                            scatter_data_rear = scatter_data_rear[~scatter_data_rear[clip_col_name_rear].isin(exclude_clips)]

                    center_sections_rear = scatter_data_rear[center_section_col].unique()

                    for idx, center in enumerate(sorted(center_sections_rear)):
                        center_data = scatter_data_rear[scatter_data_rear[center_section_col] == center]

                        fig_rear.add_trace(go.Scatter(
                            x=center_data['LR_Damper_Length'].tolist(),
                            y=center_data['RR_Damper_Length'].tolist(),
                            mode='markers',
                            name=str(center),
                            marker=dict(
                                size=12,
                                color=colors[idx % len(colors)],
                                line=dict(width=1, color='white')
                            ),
                            text=center_data[clip_col_name_rear].tolist(),
                            hovertemplate='<b>Center Section:</b> %{fullData.name}<br>' +
                                        f'<b>{clip_col_name_rear}:</b> %{{text}}<br>' +
                                        '<b>LR Length:</b> %{x:.4f}<br>' +
                                        '<b>RR Length:</b> %{y:.4f}<br>' +
                                        '<extra></extra>'
                        ))

                    legend_title_rear = "Center Section"

                else:
                    # Clip View: Color by clip, shape by center section
                    if view_mode == "Clip View" and not selected_centers:
                        st.warning("Please select at least one center section to display")
                    else:
                        scatter_data_rear = rear_data_all[rear_data_all[center_section_col].isin(selected_centers)].copy()
                        clip_col_name_rear = 'Rear_Clip' if using_multi_sheet else clip_col
                        unique_clips_rear = sorted(scatter_data_rear[clip_col_name_rear].unique())
                        selected_centers_sorted = sorted(selected_centers)

                        for center_idx, center in enumerate(selected_centers_sorted):
                            for clip_idx, clip in enumerate(unique_clips_rear):
                                clip_center_data = scatter_data_rear[
                                    (scatter_data_rear[center_section_col] == center) &
                                    (scatter_data_rear[clip_col_name_rear] == clip)
                                ]

                                if len(clip_center_data) > 0:
                                    fig_rear.add_trace(go.Scatter(
                                        x=clip_center_data['LR_Damper_Length'].tolist(),
                                        y=clip_center_data['RR_Damper_Length'].tolist(),
                                        mode='markers',
                                        name=f"{clip}",
                                        legendgroup=clip,
                                        marker=dict(
                                            size=14,
                                            color=colors[clip_idx % len(colors)],
                                            symbol=marker_symbols[center_idx % len(marker_symbols)],
                                            line=dict(width=1, color='white')
                                        ),
                                        text=[f"Center: {center}"] * len(clip_center_data),
                                        hovertemplate=f'<b>{clip_col_name_rear}:</b> {clip}<br>' +
                                                    '<b>Center Section:</b> %{text}<br>' +
                                                    '<b>LR Length:</b> %{x:.4f}<br>' +
                                                    '<b>RR Length:</b> %{y:.4f}<br>' +
                                                    '<extra></extra>',
                                        showlegend=(center_idx == 0)  # Only show legend for first center section
                                    ))

                        legend_title_rear = f"Clip (Shapes: {', '.join(selected_centers_sorted)})"

                # Update layout for rear plot
                fig_rear.update_layout(
                    xaxis_title="LR Damper Length",
                    yaxis_title="RR Damper Length",
                    hovermode='closest',
                    legend=dict(
                        title=legend_title_rear,
                        yanchor="top",
                        y=0.99,
                        xanchor="right",
                        x=0.99
                    ),
                    height=600,
                    xaxis=dict(tickformat='.3f'),
                    yaxis=dict(tickformat='.3f')
                )

                st.plotly_chart(fig_rear, use_container_width=True)

                # Add insights
                if using_multi_sheet:
                    corr_rear = scatter_data_rear['LR_Damper_Length'].corr(scatter_data_rear['RR_Damper_Length'])
                    st.metric("LR-RR Correlation", f"{corr_rear:.3f}")

        # Download button and detailed view at bottom of reports tab
        st.markdown("---")
        csv = results_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Complete Results as CSV",
            data=csv,
            file_name="suspension_analysis_results.csv",
            mime="text/csv"
        )

        with st.expander("🔍 View All Columns"):
            st.dataframe(results_df, use_container_width=True)

        # Selector Tab
        with selector_tab:

            # Get unique values
            all_center_sections = sorted(results_df[center_section_col].unique())

            if using_multi_sheet:
                # Get the calculated dataframes and add ranks
                df_front_calc_ranks = st.session_state['df_front_calc'].copy()
                df_rear_calc_ranks = st.session_state['df_rear_calc'].copy()

                # Calculate ranks
                df_front_calc_ranks['LF_Rank'] = df_front_calc_ranks['LF_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_front_calc_ranks['RF_Rank'] = df_front_calc_ranks['RF_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_front_calc_ranks['Front_Weighted_Score'] = (df_front_calc_ranks['LF_Rank'] * 2) + (df_front_calc_ranks['RF_Rank'] * 1)
                df_front_calc_ranks['Front_Rank'] = df_front_calc_ranks['Front_Weighted_Score'].rank(method='min').astype(int)

                df_rear_calc_ranks['LR_Rank'] = df_rear_calc_ranks['LR_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_rear_calc_ranks['RR_Rank'] = df_rear_calc_ranks['RR_Damper_Length'].rank(ascending=False, method='min').astype(int)
                df_rear_calc_ranks['Rear_Weighted_Score'] = (df_rear_calc_ranks['LR_Rank'] * 2) + (df_rear_calc_ranks['RR_Rank'] * 1)
                df_rear_calc_ranks['Rear_Rank'] = df_rear_calc_ranks['Rear_Weighted_Score'].rank(method='min').astype(int)

                all_front_clips = sorted(df_front_calc_ranks[clip_col].unique())
                all_rear_clips = sorted(df_rear_calc_ranks[clip_col].unique())

                # Initialize corner weightings in session state
                if 'corner_weights' not in st.session_state:
                    st.session_state['corner_weights'] = {
                        'LF': 25.0,
                        'RF': 25.0,
                        'LR': 25.0,
                        'RR': 25.0
                    }

                # Function to calculate optimal assignments based on weightings
                def calculate_optimal_assignments(lf_weight, rf_weight, lr_weight, rr_weight):
                    assignments = {}
                    used_front_clips = set()
                    used_rear_clips = set()
                    center_best_combos = []

                    for cs in all_center_sections:
                        best_score = float('inf')
                        best_front = None
                        best_rear = None

                        # Try all available front clips
                        for front_clip in all_front_clips:
                            if front_clip in used_front_clips:
                                continue

                            # Get front data for this combo
                            front_mask = (df_front_calc_ranks[center_section_col] == cs) & (df_front_calc_ranks[clip_col] == front_clip)
                            front_rows = df_front_calc_ranks[front_mask]

                            if len(front_rows) == 0:
                                continue

                            lf_rank = front_rows.iloc[0]['LF_Rank']
                            rf_rank = front_rows.iloc[0]['RF_Rank']

                            # Try all available rear clips
                            for rear_clip in all_rear_clips:
                                if rear_clip in used_rear_clips:
                                    continue

                                # Get rear data for this combo
                                rear_mask = (df_rear_calc_ranks[center_section_col] == cs) & (df_rear_calc_ranks[clip_col] == rear_clip)
                                rear_rows = df_rear_calc_ranks[rear_mask]

                                if len(rear_rows) == 0:
                                    continue

                                lr_rank = rear_rows.iloc[0]['LR_Rank']
                                rr_rank = rear_rows.iloc[0]['RR_Rank']

                                # Combined score using corner weightings
                                combined_score = (lf_rank * lf_weight/100) + (rf_rank * rf_weight/100) + \
                                               (lr_rank * lr_weight/100) + (rr_rank * rr_weight/100)

                                if combined_score < best_score:
                                    best_score = combined_score
                                    best_front = front_clip
                                    best_rear = rear_clip

                        # Assign the best combination found
                        if best_front and best_rear:
                            center_best_combos.append({
                                'center': cs,
                                'front_clip': best_front,
                                'rear_clip': best_rear,
                                'score': best_score
                            })
                            used_front_clips.add(best_front)
                            used_rear_clips.add(best_rear)
                        else:
                            # Fallback: assign any unused clips
                            fallback_front = next((c for c in all_front_clips if c not in used_front_clips), all_front_clips[0])
                            fallback_rear = next((c for c in all_rear_clips if c not in used_rear_clips), all_rear_clips[0])
                            center_best_combos.append({
                                'center': cs,
                                'front_clip': fallback_front,
                                'rear_clip': fallback_rear,
                                'score': float('inf')
                            })
                            used_front_clips.add(fallback_front)
                            used_rear_clips.add(fallback_rear)

                    # Store assignments
                    for combo in center_best_combos:
                        assignments[combo['center']] = {
                            'front_clip': combo['front_clip'],
                            'rear_clip': combo['rear_clip']
                        }

                    return assignments

                # Initialize session state for clip assignments if not exists
                if 'lineup_assignments' not in st.session_state:
                    st.session_state['lineup_assignments'] = calculate_optimal_assignments(
                        st.session_state['corner_weights']['LF'],
                        st.session_state['corner_weights']['RF'],
                        st.session_state['corner_weights']['LR'],
                        st.session_state['corner_weights']['RR']
                    )

                # Initialize track types if not exists
                if 'track_types' not in st.session_state:
                    st.session_state['track_types'] = {cs: 'INT' for cs in all_center_sections}

                # Corner weighting controls
                weight_cols = st.columns([1, 1, 1, 1, 1.2])

                with weight_cols[0]:
                    lf_weight = st.number_input("LF %", min_value=0.0, max_value=100.0,
                                               value=st.session_state['corner_weights']['LF'],
                                               step=5.0, key='lf_weight_input')
                with weight_cols[1]:
                    rf_weight = st.number_input("RF %", min_value=0.0, max_value=100.0,
                                               value=st.session_state['corner_weights']['RF'],
                                               step=5.0, key='rf_weight_input')
                with weight_cols[2]:
                    lr_weight = st.number_input("LR %", min_value=0.0, max_value=100.0,
                                               value=st.session_state['corner_weights']['LR'],
                                               step=5.0, key='lr_weight_input')
                with weight_cols[3]:
                    rr_weight = st.number_input("RR %", min_value=0.0, max_value=100.0,
                                               value=st.session_state['corner_weights']['RR'],
                                               step=5.0, key='rr_weight_input')

                total_weight = lf_weight + rf_weight + lr_weight + rr_weight

                with weight_cols[4]:
                    st.markdown(f"**Total: {total_weight:.0f}%**")
                    if abs(total_weight - 100.0) > 0.01:
                        calculate_button = st.button("Calculate", disabled=True)
                    else:
                        calculate_button = st.button("Calculate", type="primary")

                        if calculate_button:
                            st.session_state['corner_weights']['LF'] = lf_weight
                            st.session_state['corner_weights']['RF'] = rf_weight
                            st.session_state['corner_weights']['LR'] = lr_weight
                            st.session_state['corner_weights']['RR'] = rr_weight

                            st.session_state['lineup_assignments'] = calculate_optimal_assignments(
                                lf_weight, rf_weight, lr_weight, rr_weight
                            )
                            st.rerun()

                st.markdown("")

                # Initialize manual order flag
                if 'manual_order_mode' not in st.session_state:
                    st.session_state['manual_order_mode'] = False

                # When Calculate is pressed, reset to sorted mode
                if 'last_calculate_time' not in st.session_state:
                    st.session_state['last_calculate_time'] = 0

                if calculate_button:
                    st.session_state['manual_order_mode'] = False
                    st.session_state['last_calculate_time'] += 1

                # Build results as we go through each center section
                lineup_results = []

                # Determine sort order
                if st.session_state['manual_order_mode']:
                    # Keep the original sorted order
                    sorted_centers = sorted(all_center_sections)
                else:
                    # Calculate weighted scores for each center section to sort them
                    center_scores = []
                    for center in all_center_sections:
                        front_clip = st.session_state['lineup_assignments'][center]['front_clip']
                        rear_clip = st.session_state['lineup_assignments'][center]['rear_clip']

                        # Get front and rear data
                        front_mask = (df_front_calc_ranks[center_section_col] == center) & (df_front_calc_ranks[clip_col] == front_clip)
                        front_row = df_front_calc_ranks[front_mask]

                        rear_mask = (df_rear_calc_ranks[center_section_col] == center) & (df_rear_calc_ranks[clip_col] == rear_clip)
                        rear_row = df_rear_calc_ranks[rear_mask]

                        if len(front_row) > 0 and len(rear_row) > 0:
                            front_data = front_row.iloc[0]
                            rear_data = rear_row.iloc[0]

                            # Calculate weighted score using current corner weights
                            lf_weight = st.session_state['corner_weights']['LF'] / 100
                            rf_weight = st.session_state['corner_weights']['RF'] / 100
                            lr_weight = st.session_state['corner_weights']['LR'] / 100
                            rr_weight = st.session_state['corner_weights']['RR'] / 100

                            weighted_score = (front_data['LF_Rank'] * lf_weight) + \
                                           (front_data['RF_Rank'] * rf_weight) + \
                                           (rear_data['LR_Rank'] * lr_weight) + \
                                           (rear_data['RR_Rank'] * rr_weight)

                            center_scores.append((center, weighted_score))
                        else:
                            center_scores.append((center, float('inf')))

                    # Sort center sections by weighted score (best first)
                    sorted_centers = [center for center, score in sorted(center_scores, key=lambda x: x[1])]

                # Create two side-by-side tables
                table_cols = st.columns([1, 1])

                # Build data for both tables
                front_table_data = []
                rear_table_data = []

                for center in sorted_centers:
                    selected_front = st.session_state['lineup_assignments'][center]['front_clip']
                    selected_rear = st.session_state['lineup_assignments'][center]['rear_clip']

                    # Get front data
                    front_mask = (df_front_calc_ranks[center_section_col] == center) & (df_front_calc_ranks[clip_col] == selected_front)
                    front_row = df_front_calc_ranks[front_mask]

                    # Get rear data
                    rear_mask = (df_rear_calc_ranks[center_section_col] == center) & (df_rear_calc_ranks[clip_col] == selected_rear)
                    rear_row = df_rear_calc_ranks[rear_mask]

                    if len(front_row) > 0 and len(rear_row) > 0:
                        front_data = front_row.iloc[0]
                        rear_data = rear_row.iloc[0]

                        front_table_data.append({
                            'Track_Type': st.session_state['track_types'][center],
                            'Center_Section': center,
                            'Front_Clip': selected_front,
                            'LF_Length': front_data['LF_Damper_Length'],
                            'RF_Length': front_data['RF_Damper_Length'],
                            'LF_Rank': int(front_data['LF_Rank']),
                            'RF_Rank': int(front_data['RF_Rank']),
                            'Front_Rank': int(front_data['Front_Rank'])
                        })

                        rear_table_data.append({
                            'Center_Section': center,
                            'Rear_Clip': selected_rear,
                            'LR_Length': rear_data['LR_Damper_Length'],
                            'RR_Length': rear_data['RR_Damper_Length'],
                            'LR_Rank': int(rear_data['LR_Rank']),
                            'RR_Rank': int(rear_data['RR_Rank']),
                            'Rear_Rank': int(rear_data['Rear_Rank'])
                        })

                        # Store for summary
                        lineup_results.append({
                            'Center_Section': center,
                            'Front_Clip': selected_front,
                            'Rear_Clip': selected_rear,
                            'LF_Rank': int(front_data['LF_Rank']),
                            'RF_Rank': int(front_data['RF_Rank']),
                            'LR_Rank': int(rear_data['LR_Rank']),
                            'RR_Rank': int(rear_data['RR_Rank']),
                            'Front_Rank': int(front_data['Front_Rank']),
                            'Rear_Rank': int(rear_data['Rear_Rank']),
                            'LF_Length': front_data['LF_Damper_Length'],
                            'RF_Length': front_data['RF_Damper_Length'],
                            'LR_Length': rear_data['LR_Damper_Length'],
                            'RR_Length': rear_data['RR_Damper_Length'],
                            'Front_Score': front_data['Front_Weighted_Score'],
                            'Rear_Score': rear_data['Rear_Weighted_Score']
                        })

                # Create dataframes
                df_front_table = pd.DataFrame(front_table_data)
                df_rear_table = pd.DataFrame(rear_table_data)

                # Calculate dynamic height based on number of rows (35px per row + 38px header)
                num_rows = len(df_front_table)
                table_height = min(35 * num_rows + 38, 400)  # Cap at 400px max for compactness

                # Detect duplicates
                front_clip_counts = df_front_table['Front_Clip'].value_counts()
                rear_clip_counts = df_rear_table['Rear_Clip'].value_counts()
                front_duplicates = set(front_clip_counts[front_clip_counts > 1].index)
                rear_duplicates = set(rear_clip_counts[rear_clip_counts > 1].index)

                # Front Table
                with table_cols[0]:
                    st.markdown("**Front Clip Selection**")

                    # Editable dataframe with progress bars
                    edited_front = st.data_editor(
                        df_front_table,
                        use_container_width=True,
                        hide_index=True,
                        height=table_height,
                        column_config={
                            "Track_Type": st.column_config.SelectboxColumn(
                                "Track",
                                options=['INT', 'ST', 'RC', 'Utility', 'SSW', 'Backup'],
                                required=True
                            ),
                            "Center_Section": st.column_config.TextColumn(
                                "Center",
                                disabled=True
                            ),
                            "Front_Clip": st.column_config.SelectboxColumn(
                                "Front Clip",
                                options=all_front_clips,
                                required=True
                            ),
                            "LF_Length": st.column_config.ProgressColumn(
                                "LF Length",
                                format="%.3f",
                                min_value=df_front_table['LF_Length'].min(),
                                max_value=df_front_table['LF_Length'].max()
                            ),
                            "RF_Length": st.column_config.ProgressColumn(
                                "RF Length",
                                format="%.3f",
                                min_value=df_front_table['RF_Length'].min(),
                                max_value=df_front_table['RF_Length'].max()
                            ),
                            "LF_Rank": st.column_config.TextColumn(
                                "LF",
                                disabled=True
                            ),
                            "RF_Rank": st.column_config.TextColumn(
                                "RF",
                                disabled=True
                            ),
                            "Front_Rank": st.column_config.TextColumn(
                                "Front",
                                disabled=True
                            )
                        },
                        key='front_table_editor'
                    )

                    # Check if any changes were made and update session state
                    changes_made = False
                    for idx, row in edited_front.iterrows():
                        center = row['Center_Section']
                        new_front_clip = row['Front_Clip']
                        new_track_type = row['Track_Type']

                        if st.session_state['lineup_assignments'][center]['front_clip'] != new_front_clip:
                            st.session_state['manual_order_mode'] = True
                            st.session_state['lineup_assignments'][center]['front_clip'] = new_front_clip
                            changes_made = True

                        if st.session_state['track_types'][center] != new_track_type:
                            st.session_state['track_types'][center] = new_track_type
                            changes_made = True

                # Rear Table
                with table_cols[1]:
                    st.markdown("**Rear Clip Selection**")

                    # Editable dataframe with progress bars
                    edited_rear = st.data_editor(
                        df_rear_table,
                        use_container_width=True,
                        hide_index=True,
                        height=table_height,
                        column_config={
                            "Center_Section": st.column_config.TextColumn(
                                "Center",
                                disabled=True
                            ),
                            "Rear_Clip": st.column_config.SelectboxColumn(
                                "Rear Clip",
                                options=all_rear_clips,
                                required=True
                            ),
                            "LR_Length": st.column_config.ProgressColumn(
                                "LR Length",
                                format="%.3f",
                                min_value=df_rear_table['LR_Length'].min(),
                                max_value=df_rear_table['LR_Length'].max()
                            ),
                            "RR_Length": st.column_config.ProgressColumn(
                                "RR Length",
                                format="%.3f",
                                min_value=df_rear_table['RR_Length'].min(),
                                max_value=df_rear_table['RR_Length'].max()
                            ),
                            "LR_Rank": st.column_config.TextColumn(
                                "LR",
                                disabled=True
                            ),
                            "RR_Rank": st.column_config.TextColumn(
                                "RR",
                                disabled=True
                            ),
                            "Rear_Rank": st.column_config.TextColumn(
                                "Rear",
                                disabled=True
                            )
                        },
                        key='rear_table_editor'
                    )

                    # Check if any changes were made and update session state
                    for idx, row in edited_rear.iterrows():
                        center = row['Center_Section']
                        new_rear_clip = row['Rear_Clip']

                        if st.session_state['lineup_assignments'][center]['rear_clip'] != new_rear_clip:
                            st.session_state['manual_order_mode'] = True
                            st.session_state['lineup_assignments'][center]['rear_clip'] = new_rear_clip
                            changes_made = True

                # If changes were made, trigger rerun to refresh the table with updated data
                if changes_made:
                    st.rerun()

                # Show duplicate warning summary if any exist
                if front_duplicates or rear_duplicates:
                    st.markdown("")
                    warning_parts = []
                    if front_duplicates:
                        warning_parts.append(f"Front: {', '.join(front_duplicates)}")
                    if rear_duplicates:
                        warning_parts.append(f"Rear: {', '.join(rear_duplicates)}")
                    st.warning(f"⚠️ Duplicate clips detected - {' | '.join(warning_parts)}")

                # "What If" Calculator Section
                st.markdown("---")

                # Center section selector for What If analysis
                whatif_center = st.selectbox(
                    "What If Analysis - Select Center Section:",
                    options=sorted_centers,
                    key='whatif_center_selector'
                )

                # Get current assignments for the selected center
                current_front_clip = st.session_state['lineup_assignments'][whatif_center]['front_clip']
                current_rear_clip = st.session_state['lineup_assignments'][whatif_center]['rear_clip']

                # Get current damper lengths
                current_front_mask = (df_front_calc_ranks[center_section_col] == whatif_center) & \
                                    (df_front_calc_ranks[clip_col] == current_front_clip)
                current_front_data = df_front_calc_ranks[current_front_mask].iloc[0]
                current_lf_length = current_front_data['LF_Damper_Length']
                current_rf_length = current_front_data['RF_Damper_Length']

                current_rear_mask = (df_rear_calc_ranks[center_section_col] == whatif_center) & \
                                   (df_rear_calc_ranks[clip_col] == current_rear_clip)
                current_rear_data = df_rear_calc_ranks[current_rear_mask].iloc[0]
                current_lr_length = current_rear_data['LR_Damper_Length']
                current_rr_length = current_rear_data['RR_Damper_Length']

                # Build What If tables
                whatif_cols = st.columns([1, 1])

                # Build assignment tracking for all center sections
                all_front_assignments = {}
                all_rear_assignments = {}
                for cs in sorted_centers:
                    assigned_front = st.session_state['lineup_assignments'][cs]['front_clip']
                    assigned_rear = st.session_state['lineup_assignments'][cs]['rear_clip']

                    if assigned_front not in all_front_assignments:
                        all_front_assignments[assigned_front] = []
                    all_front_assignments[assigned_front].append(cs)

                    if assigned_rear not in all_rear_assignments:
                        all_rear_assignments[assigned_rear] = []
                    all_rear_assignments[assigned_rear].append(cs)

                # Front What If Table
                with whatif_cols[0]:
                    st.markdown(f"**Front Clips** (Current: {current_front_clip})")

                    front_whatif_data = []
                    for clip in all_front_clips:
                        clip_mask = (df_front_calc_ranks[center_section_col] == whatif_center) & \
                                   (df_front_calc_ranks[clip_col] == clip)
                        clip_data = df_front_calc_ranks[clip_mask]

                        if len(clip_data) > 0:
                            clip_row = clip_data.iloc[0]
                            lf_delta = clip_row['LF_Damper_Length'] - current_lf_length
                            rf_delta = clip_row['RF_Damper_Length'] - current_rf_length

                            # Add color indicator
                            lf_indicator = "🟢" if lf_delta > 0 else ("🔴" if lf_delta < 0 else "⚪")
                            rf_indicator = "🟢" if rf_delta > 0 else ("🔴" if rf_delta < 0 else "⚪")

                            # Check if clip is assigned to another center
                            if clip in all_front_assignments:
                                assigned_centers = [cs for cs in all_front_assignments[clip] if cs != whatif_center]
                                if assigned_centers:
                                    assigned_to = f"✗ {assigned_centers[0]}"
                                else:
                                    assigned_to = "✓"
                            else:
                                assigned_to = "✓"

                            front_whatif_data.append({
                                'Clip': clip,
                                'Available': assigned_to,
                                'LF Δ': f"{lf_indicator} {lf_delta:+.3f}",
                                'RF Δ': f"{rf_indicator} {rf_delta:+.3f}"
                            })

                    df_front_whatif = pd.DataFrame(front_whatif_data)

                    # Calculate height to show all rows without scrolling
                    whatif_height = 35 * len(df_front_whatif) + 38

                    st.dataframe(
                        df_front_whatif,
                        use_container_width=True,
                        height=whatif_height,
                        hide_index=True
                    )

                # Rear What If Table
                with whatif_cols[1]:
                    st.markdown(f"**Rear Clips** (Current: {current_rear_clip})")

                    rear_whatif_data = []
                    for clip in all_rear_clips:
                        clip_mask = (df_rear_calc_ranks[center_section_col] == whatif_center) & \
                                   (df_rear_calc_ranks[clip_col] == clip)
                        clip_data = df_rear_calc_ranks[clip_mask]

                        if len(clip_data) > 0:
                            clip_row = clip_data.iloc[0]
                            lr_delta = clip_row['LR_Damper_Length'] - current_lr_length
                            rr_delta = clip_row['RR_Damper_Length'] - current_rr_length

                            # Add color indicator
                            lr_indicator = "🟢" if lr_delta > 0 else ("🔴" if lr_delta < 0 else "⚪")
                            rr_indicator = "🟢" if rr_delta > 0 else ("🔴" if rr_delta < 0 else "⚪")

                            # Check if clip is assigned to another center
                            if clip in all_rear_assignments:
                                assigned_centers = [cs for cs in all_rear_assignments[clip] if cs != whatif_center]
                                if assigned_centers:
                                    assigned_to = f"✗ {assigned_centers[0]}"
                                else:
                                    assigned_to = "✓"
                            else:
                                assigned_to = "✓"

                            rear_whatif_data.append({
                                'Clip': clip,
                                'Available': assigned_to,
                                'LR Δ': f"{lr_indicator} {lr_delta:+.3f}",
                                'RR Δ': f"{rr_indicator} {rr_delta:+.3f}"
                            })

                    df_rear_whatif = pd.DataFrame(rear_whatif_data)

                    # Calculate height to show all rows without scrolling
                    whatif_rear_height = 35 * len(df_rear_whatif) + 38

                    st.dataframe(
                        df_rear_whatif,
                        use_container_width=True,
                        height=whatif_rear_height,
                        hide_index=True
                    )

                lineup_df = pd.DataFrame(lineup_results)

                if len(lineup_df) > 0:
                    # Fleet Overview Summary
                    st.markdown("")
                    st.markdown("---")

                    summary_cols = st.columns(6)
                    with summary_cols[0]:
                        avg_lf = lineup_df['LF_Rank'].mean()
                        st.metric("Avg LF", f"#{avg_lf:.1f}")
                    with summary_cols[1]:
                        avg_rf = lineup_df['RF_Rank'].mean()
                        st.metric("Avg RF", f"#{avg_rf:.1f}")
                    with summary_cols[2]:
                        avg_lr = lineup_df['LR_Rank'].mean()
                        st.metric("Avg LR", f"#{avg_lr:.1f}")
                    with summary_cols[3]:
                        avg_rr = lineup_df['RR_Rank'].mean()
                        st.metric("Avg RR", f"#{avg_rr:.1f}")
                    with summary_cols[4]:
                        avg_front = lineup_df['Front_Rank'].mean()
                        st.metric("Avg Front", f"#{avg_front:.1f}")
                    with summary_cols[5]:
                        avg_rear = lineup_df['Rear_Rank'].mean()
                        st.metric("Avg Rear", f"#{avg_rear:.1f}")

            else:
                st.info("Lineup Builder is only available in multi-sheet mode (separate front and rear clip data)")

        # Attribute Compare Tab
        with attribute_tab:

            # Get configuration from session state
            config = st.session_state.get('config', {})

            # Front/Rear selection
            front_rear_select = st.radio(
                "Select Analysis:",
                options=["Front (LF/RF)", "Rear (LR/RR)"],
                horizontal=True,
                key='attribute_front_rear'
            )

            is_front = front_rear_select == "Front (LF/RF)"

            # Prepare data based on selection
            if using_multi_sheet:
                if is_front:
                    df_attribute = st.session_state.get('df_front_calc', results_df).copy()
                    damper_col_options = ['LF_Damper_Length', 'RF_Damper_Length']
                    corner_prefix = ['lf', 'rf']
                else:
                    df_attribute = st.session_state.get('df_rear_calc', results_df).copy()
                    damper_col_options = ['LR_Damper_Length', 'RR_Damper_Length']
                    corner_prefix = ['lr', 'rr']
            else:
                df_attribute = results_df.copy()
                if is_front:
                    damper_col_options = ['LF_Damper_Length', 'RF_Damper_Length']
                    corner_prefix = ['lf', 'rf']
                else:
                    damper_col_options = ['LR_Damper_Length', 'RR_Damper_Length']
                    corner_prefix = ['lr', 'rr']

            # Build list of available attribute columns
            attribute_options = []
            for corner in corner_prefix:
                # Upper damper mounts
                for axis in ['x', 'y', 'z']:
                    col_name = config.get(f'{corner}_upper_{axis}')
                    if col_name and col_name in df_attribute.columns:
                        attribute_options.append((col_name, f"{corner.upper()} Upper {axis.upper()}"))

                # LCA front mounts
                for axis in ['x', 'y', 'z']:
                    col_name = config.get(f'{corner}_lca_front_{axis}')
                    if col_name and col_name in df_attribute.columns:
                        attribute_options.append((col_name, f"{corner.upper()} LCA Front {axis.upper()}"))

                # LCA rear mounts
                for axis in ['x', 'y', 'z']:
                    col_name = config.get(f'{corner}_lca_rear_{axis}')
                    if col_name and col_name in df_attribute.columns:
                        attribute_options.append((col_name, f"{corner.upper()} LCA Rear {axis.upper()}"))

            if not attribute_options:
                st.warning("No attribute columns found. Please configure your data in the Data Configuration tab.")
            else:
                # Selection controls
                col1, col2 = st.columns(2)

                with col1:
                    y_axis = st.selectbox(
                        "Y-Axis (Damper Length):",
                        options=damper_col_options,
                        format_func=lambda x: x.replace('_', ' '),
                        key='attribute_y_axis'
                    )

                with col2:
                    x_axis_display = st.selectbox(
                        "X-Axis (Attribute):",
                        options=[opt[1] for opt in attribute_options],
                        key='attribute_x_axis_display'
                    )
                    # Get actual column name
                    x_axis = [opt[0] for opt in attribute_options if opt[1] == x_axis_display][0]

                # Color by option
                color_by = st.selectbox(
                    "Color by:",
                    options=[center_section_col, clip_col],
                    key='attribute_color_by'
                )

                # Create scatter plot
                fig_attr = go.Figure()

                # Get unique values for coloring
                unique_values = sorted(df_attribute[color_by].unique())
                colors = px.colors.qualitative.Plotly

                for idx, value in enumerate(unique_values):
                    value_data = df_attribute[df_attribute[color_by] == value]

                    fig_attr.add_trace(go.Scatter(
                        x=value_data[x_axis].tolist(),
                        y=value_data[y_axis].tolist(),
                        mode='markers',
                        name=str(value),
                        marker=dict(
                            size=10,
                            color=colors[idx % len(colors)],
                            line=dict(width=1, color='white')
                        ),
                        text=value_data[clip_col if color_by == center_section_col else center_section_col].tolist(),
                        hovertemplate=f'<b>{color_by}:</b> %{{fullData.name}}<br>' +
                                    f'<b>{"Clip" if color_by == center_section_col else "Center Section"}:</b> %{{text}}<br>' +
                                    f'<b>{x_axis_display}:</b> %{{x:.4f}}<br>' +
                                    f'<b>{y_axis.replace("_", " ")}:</b> %{{y:.4f}}<br>' +
                                    '<extra></extra>'
                    ))

                # Calculate correlation
                correlation = df_attribute[[x_axis, y_axis]].corr().iloc[0, 1]

                fig_attr.update_layout(
                    title=f"{y_axis.replace('_', ' ')} vs {x_axis_display}<br><sub>Correlation: {correlation:.3f}</sub>",
                    xaxis_title=x_axis_display,
                    yaxis_title=y_axis.replace('_', ' '),
                    height=600,
                    hovermode='closest',
                    legend=dict(
                        title=color_by.replace('_', ' '),
                        yanchor="top",
                        y=0.99,
                        xanchor="right",
                        x=0.99
                    ),
                    xaxis=dict(tickformat='.3f'),
                    yaxis=dict(tickformat='.3f')
                )

                st.plotly_chart(fig_attr, use_container_width=True)

                # Show statistics
                st.markdown("### 📊 Statistics")
                stat_cols = st.columns(3)

                with stat_cols[0]:
                    st.metric("Correlation", f"{correlation:.3f}")

                with stat_cols[1]:
                    st.metric(f"Avg {x_axis_display}", f"{df_attribute[x_axis].mean():.3f}")

                with stat_cols[2]:
                    st.metric(f"Avg {y_axis.replace('_', ' ')}", f"{df_attribute[y_axis].mean():.4f}")

        # 3D Visualizer Tab
        with visualizer_tab:

            # Combination selector
            if using_multi_sheet:
                vis_cols = st.columns(3)
                with vis_cols[0]:
                    center_sections = sorted(results_df[center_section_col].unique())
                    selected_center = st.selectbox("Select Center Section", options=center_sections, key='vis_center')
                with vis_cols[1]:
                    front_clips = sorted(results_df['Front_Clip'].unique())
                    selected_front_clip = st.selectbox("Select Front Clip", options=front_clips, key='vis_front_clip')
                with vis_cols[2]:
                    rear_clips = sorted(results_df['Rear_Clip'].unique())
                    selected_rear_clip = st.selectbox("Select Rear Clip", options=rear_clips, key='vis_rear_clip')
            else:
                vis_cols = st.columns(2)
                with vis_cols[0]:
                    center_sections = sorted(results_df[center_section_col].unique())
                    selected_center = st.selectbox("Select Center Section", options=center_sections, key='vis_center')
                with vis_cols[1]:
                    clips = sorted(results_df[clip_col].unique())
                    selected_clip = st.selectbox("Select Clip", options=clips, key='vis_clip')

            # Debug: Show column mappings
            with st.expander("🔍 Debug: Column Mappings", expanded=False):
                st.markdown("**Front Clip (LF/RF)**")
                col1, col2 = st.columns(2)
                with col1:
                    st.caption("**LF (Left Front)**")
                    st.text(f"Upper: {lf_upper_x}, {lf_upper_y}, {lf_upper_z}")
                    st.text(f"LCA Front: {lf_lca_front_x}, {lf_lca_front_y}, {lf_lca_front_z}")
                    st.text(f"LCA Rear: {lf_lca_rear_x}, {lf_lca_rear_y}, {lf_lca_rear_z}")
                    st.text(f"Y-Offset: {lf_y_offset}")
                with col2:
                    st.caption("**RF (Right Front)**")
                    st.text(f"Upper: {rf_upper_x}, {rf_upper_y}, {rf_upper_z}")
                    st.text(f"LCA Front: {rf_lca_front_x}, {rf_lca_front_y}, {rf_lca_front_z}")
                    st.text(f"LCA Rear: {rf_lca_rear_x}, {rf_lca_rear_y}, {rf_lca_rear_z}")
                    st.text(f"Y-Offset: {rf_y_offset}")

                st.markdown("**Rear Clip (LR/RR)**")
                col3, col4 = st.columns(2)
                with col3:
                    st.caption("**LR (Left Rear)**")
                    st.text(f"Upper: {lr_upper_x}, {lr_upper_y}, {lr_upper_z}")
                    st.text(f"LCA Front: {lr_lca_front_x}, {lr_lca_front_y}, {lr_lca_front_z}")
                    st.text(f"LCA Rear: {lr_lca_rear_x}, {lr_lca_rear_y}, {lr_lca_rear_z}")
                    st.text(f"Y-Offset: {lr_y_offset}")
                with col4:
                    st.caption("**RR (Right Rear)**")
                    st.text(f"Upper: {rr_upper_x}, {rr_upper_y}, {rr_upper_z}")
                    st.text(f"LCA Front: {rr_lca_front_x}, {rr_lca_front_y}, {rr_lca_front_z}")
                    st.text(f"LCA Rear: {rr_lca_rear_x}, {rr_lca_rear_y}, {rr_lca_rear_z}")
                    st.text(f"Y-Offset: {rr_y_offset}")

            # Extract coordinates based on mode
            if using_multi_sheet:
                # Get front data from front sheet
                df_front = st.session_state['df_front']
                mask_front = (df_front[center_section_col] == selected_center) & (df_front[clip_col] == selected_front_clip)
                front_row = df_front[mask_front]

                # Get rear data from rear sheet
                df_rear = st.session_state['df_rear']
                mask_rear = (df_rear[center_section_col] == selected_center) & (df_rear[clip_col] == selected_rear_clip)
                rear_row = df_rear[mask_rear]

                if len(front_row) == 0 or len(rear_row) == 0:
                    st.error(f"❌ No data found for combination: {selected_center} + Front: {selected_front_clip} + Rear: {selected_rear_clip}")
                    coords = None
                else:
                    front_data = front_row.iloc[0]
                    rear_data = rear_row.iloc[0]

                    # Extract coordinates from appropriate sheets
                    coords = {
                        'lf_upper': [front_data[lf_upper_x], front_data[lf_upper_y], front_data[lf_upper_z]],
                        'rf_upper': [front_data[rf_upper_x], front_data[rf_upper_y], front_data[rf_upper_z]],
                        'lr_upper': [rear_data[lr_upper_x], rear_data[lr_upper_y], rear_data[lr_upper_z]],
                        'rr_upper': [rear_data[rr_upper_x], rear_data[rr_upper_y], rear_data[rr_upper_z]],

                        'lf_lca_front': [front_data[lf_lca_front_x], front_data[lf_lca_front_y], front_data[lf_lca_front_z]],
                        'lf_lca_rear': [front_data[lf_lca_rear_x], front_data[lf_lca_rear_y], front_data[lf_lca_rear_z]],
                        'rf_lca_front': [front_data[rf_lca_front_x], front_data[rf_lca_front_y], front_data[rf_lca_front_z]],
                        'rf_lca_rear': [front_data[rf_lca_rear_x], front_data[rf_lca_rear_y], front_data[rf_lca_rear_z]],

                        'lr_lca_front': [rear_data[lr_lca_front_x], rear_data[lr_lca_front_y], rear_data[lr_lca_front_z]],
                        'lr_lca_rear': [rear_data[lr_lca_rear_x], rear_data[lr_lca_rear_y], rear_data[lr_lca_rear_z]],
                        'rr_lca_front': [rear_data[rr_lca_front_x], rear_data[rr_lca_front_y], rear_data[rr_lca_front_z]],
                        'rr_lca_rear': [rear_data[rr_lca_rear_x], rear_data[rr_lca_rear_y], rear_data[rr_lca_rear_z]],
                    }
            else:
                # Single sheet mode
                mask = (results_df[center_section_col] == selected_center) & (results_df[clip_col] == selected_clip)
                selected_row = results_df[mask]

                if len(selected_row) == 0:
                    st.error(f"❌ No data found for combination: {selected_center} + {selected_clip}")
                    coords = None
                else:
                    row = selected_row.iloc[0]

                    # Extract coordinates
                    coords = {
                        'lf_upper': [row[lf_upper_x], row[lf_upper_y], row[lf_upper_z]],
                        'rf_upper': [row[rf_upper_x], row[rf_upper_y], row[rf_upper_z]],
                        'lr_upper': [row[lr_upper_x], row[lr_upper_y], row[lr_upper_z]],
                        'rr_upper': [row[rr_upper_x], row[rr_upper_y], row[rr_upper_z]],

                        'lf_lca_front': [row[lf_lca_front_x], row[lf_lca_front_y], row[lf_lca_front_z]],
                        'lf_lca_rear': [row[lf_lca_rear_x], row[lf_lca_rear_y], row[lf_lca_rear_z]],
                        'rf_lca_front': [row[rf_lca_front_x], row[rf_lca_front_y], row[rf_lca_front_z]],
                        'rf_lca_rear': [row[rf_lca_rear_x], row[rf_lca_rear_y], row[rf_lca_rear_z]],

                        'lr_lca_front': [row[lr_lca_front_x], row[lr_lca_front_y], row[lr_lca_front_z]],
                        'lr_lca_rear': [row[lr_lca_rear_x], row[lr_lca_rear_y], row[lr_lca_rear_z]],
                        'rr_lca_front': [row[rr_lca_front_x], row[rr_lca_front_y], row[rr_lca_front_z]],
                        'rr_lca_rear': [row[rr_lca_rear_x], row[rr_lca_rear_y], row[rr_lca_rear_z]],
                    }

            if coords is not None:

                # Calculate LCA centers (same as in calculations)
                lf_lca_center = [(coords['lf_lca_front'][i] + coords['lf_lca_rear'][i])/2 for i in range(3)]
                rf_lca_center = [(coords['rf_lca_front'][i] + coords['rf_lca_rear'][i])/2 for i in range(3)]
                lr_lca_center = [(coords['lr_lca_front'][i] + coords['lr_lca_rear'][i])/2 for i in range(3)]
                rr_lca_center = [(coords['rr_lca_front'][i] + coords['rr_lca_rear'][i])/2 for i in range(3)]

                # Apply Y-offsets (same logic as calculations)
                lf_lower = [lf_lca_center[0], lf_lca_center[1] - abs(lf_y_offset), lf_lca_center[2]]
                rf_lower = [rf_lca_center[0], rf_lca_center[1] + abs(rf_y_offset), rf_lca_center[2]]
                lr_lower = [lr_lca_center[0], lr_lca_center[1] - abs(lr_y_offset), lr_lca_center[2]]
                rr_lower = [rr_lca_center[0], rr_lca_center[1] + abs(rr_y_offset), rr_lca_center[2]]

                # Debug: Show actual coordinate values
                with st.expander("🔍 Debug: Coordinate Values", expanded=False):
                    if using_multi_sheet:
                        st.markdown(f"**Selected: {selected_center} + Front: {selected_front_clip} + Rear: {selected_rear_clip}**")
                    else:
                        st.markdown(f"**Selected: {selected_center} + {selected_clip}**")

                    dcol1, dcol2 = st.columns(2)
                    with dcol1:
                        st.caption("**Front Corners**")
                        st.text(f"LF Upper:      X={coords['lf_upper'][0]:.3f}, Y={coords['lf_upper'][1]:.3f}, Z={coords['lf_upper'][2]:.3f}")
                        st.text(f"LF LCA Front:  X={coords['lf_lca_front'][0]:.3f}, Y={coords['lf_lca_front'][1]:.3f}, Z={coords['lf_lca_front'][2]:.3f}")
                        st.text(f"LF LCA Rear:   X={coords['lf_lca_rear'][0]:.3f}, Y={coords['lf_lca_rear'][1]:.3f}, Z={coords['lf_lca_rear'][2]:.3f}")
                        st.text(f"LF LCA Center: X={lf_lca_center[0]:.3f}, Y={lf_lca_center[1]:.3f}, Z={lf_lca_center[2]:.3f}")
                        st.text(f"LF Lower:      X={lf_lower[0]:.3f}, Y={lf_lower[1]:.3f}, Z={lf_lower[2]:.3f}")
                        st.markdown("")
                        st.text(f"RF Upper:      X={coords['rf_upper'][0]:.3f}, Y={coords['rf_upper'][1]:.3f}, Z={coords['rf_upper'][2]:.3f}")
                        st.text(f"RF LCA Front:  X={coords['rf_lca_front'][0]:.3f}, Y={coords['rf_lca_front'][1]:.3f}, Z={coords['rf_lca_front'][2]:.3f}")
                        st.text(f"RF LCA Rear:   X={coords['rf_lca_rear'][0]:.3f}, Y={coords['rf_lca_rear'][1]:.3f}, Z={coords['rf_lca_rear'][2]:.3f}")
                        st.text(f"RF LCA Center: X={rf_lca_center[0]:.3f}, Y={rf_lca_center[1]:.3f}, Z={rf_lca_center[2]:.3f}")
                        st.text(f"RF Lower:      X={rf_lower[0]:.3f}, Y={rf_lower[1]:.3f}, Z={rf_lower[2]:.3f}")

                    with dcol2:
                        st.caption("**Rear Corners**")
                        st.text(f"LR Upper:      X={coords['lr_upper'][0]:.3f}, Y={coords['lr_upper'][1]:.3f}, Z={coords['lr_upper'][2]:.3f}")
                        st.text(f"LR LCA Front:  X={coords['lr_lca_front'][0]:.3f}, Y={coords['lr_lca_front'][1]:.3f}, Z={coords['lr_lca_front'][2]:.3f}")
                        st.text(f"LR LCA Rear:   X={coords['lr_lca_rear'][0]:.3f}, Y={coords['lr_lca_rear'][1]:.3f}, Z={coords['lr_lca_rear'][2]:.3f}")
                        st.text(f"LR LCA Center: X={lr_lca_center[0]:.3f}, Y={lr_lca_center[1]:.3f}, Z={lr_lca_center[2]:.3f}")
                        st.text(f"LR Lower:      X={lr_lower[0]:.3f}, Y={lr_lower[1]:.3f}, Z={lr_lower[2]:.3f}")
                        st.markdown("")
                        st.text(f"RR Upper:      X={coords['rr_upper'][0]:.3f}, Y={coords['rr_upper'][1]:.3f}, Z={coords['rr_upper'][2]:.3f}")
                        st.text(f"RR LCA Front:  X={coords['rr_lca_front'][0]:.3f}, Y={coords['rr_lca_front'][1]:.3f}, Z={coords['rr_lca_front'][2]:.3f}")
                        st.text(f"RR LCA Rear:   X={coords['rr_lca_rear'][0]:.3f}, Y={coords['rr_lca_rear'][1]:.3f}, Z={coords['rr_lca_rear'][2]:.3f}")
                        st.text(f"RR LCA Center: X={rr_lca_center[0]:.3f}, Y={rr_lca_center[1]:.3f}, Z={rr_lca_center[2]:.3f}")
                        st.text(f"RR Lower:      X={rr_lower[0]:.3f}, Y={rr_lower[1]:.3f}, Z={rr_lower[2]:.3f}")

                # Create 3D plot
                fig = go.Figure()

                # Add upper mounts
                fig.add_trace(go.Scatter3d(
                    x=[coords['lf_upper'][0], coords['rf_upper'][0], coords['lr_upper'][0], coords['rr_upper'][0]],
                    y=[coords['lf_upper'][1], coords['rf_upper'][1], coords['lr_upper'][1], coords['rr_upper'][1]],
                    z=[coords['lf_upper'][2], coords['rf_upper'][2], coords['lr_upper'][2], coords['rr_upper'][2]],
                    mode='markers+text',
                    marker=dict(size=10, color='red', symbol='diamond'),
                    text=['LF Upper', 'RF Upper', 'LR Upper', 'RR Upper'],
                    textposition='top center',
                    name='Upper Mounts'
                ))

                # Add LCA front mounts
                fig.add_trace(go.Scatter3d(
                    x=[coords['lf_lca_front'][0], coords['rf_lca_front'][0], coords['lr_lca_front'][0], coords['rr_lca_front'][0]],
                    y=[coords['lf_lca_front'][1], coords['rf_lca_front'][1], coords['lr_lca_front'][1], coords['rr_lca_front'][1]],
                    z=[coords['lf_lca_front'][2], coords['rf_lca_front'][2], coords['lr_lca_front'][2], coords['rr_lca_front'][2]],
                    mode='markers',
                    marker=dict(size=6, color='green', symbol='circle'),
                    name='LCA Front Mounts'
                ))

                # Add LCA rear mounts
                fig.add_trace(go.Scatter3d(
                    x=[coords['lf_lca_rear'][0], coords['rf_lca_rear'][0], coords['lr_lca_rear'][0], coords['rr_lca_rear'][0]],
                    y=[coords['lf_lca_rear'][1], coords['rf_lca_rear'][1], coords['lr_lca_rear'][1], coords['rr_lca_rear'][1]],
                    z=[coords['lf_lca_rear'][2], coords['rf_lca_rear'][2], coords['lr_lca_rear'][2], coords['rr_lca_rear'][2]],
                    mode='markers',
                    marker=dict(size=6, color='lightgreen', symbol='circle'),
                    name='LCA Rear Mounts'
                ))

                # Add LCA centers
                fig.add_trace(go.Scatter3d(
                    x=[lf_lca_center[0], rf_lca_center[0], lr_lca_center[0], rr_lca_center[0]],
                    y=[lf_lca_center[1], rf_lca_center[1], lr_lca_center[1], rr_lca_center[1]],
                    z=[lf_lca_center[2], rf_lca_center[2], lr_lca_center[2], rr_lca_center[2]],
                    mode='markers',
                    marker=dict(size=6, color='blue', symbol='square'),
                    name='LCA Centers'
                ))

                # Add lower damper mounts
                fig.add_trace(go.Scatter3d(
                    x=[lf_lower[0], rf_lower[0], lr_lower[0], rr_lower[0]],
                    y=[lf_lower[1], rf_lower[1], lr_lower[1], rr_lower[1]],
                    z=[lf_lower[2], rf_lower[2], lr_lower[2], rr_lower[2]],
                    mode='markers+text',
                    marker=dict(size=10, color='black', symbol='circle'),
                    text=['LF Lower', 'RF Lower', 'LR Lower', 'RR Lower'],
                    textposition='bottom center',
                    name='Lower Damper Mounts'
                ))

                # Add damper lines (shocks)
                corners = [
                    ('LF', coords['lf_upper'], lf_lower, 'red'),
                    ('RF', coords['rf_upper'], rf_lower, 'blue'),
                    ('LR', coords['lr_upper'], lr_lower, 'green'),
                    ('RR', coords['rr_upper'], rr_lower, 'orange')
                ]

                for corner_name, upper, lower, color in corners:
                    length = np.sqrt(sum((upper[i] - lower[i])**2 for i in range(3)))
                    fig.add_trace(go.Scatter3d(
                        x=[upper[0], lower[0]],
                        y=[upper[1], lower[1]],
                        z=[upper[2], lower[2]],
                        mode='lines',
                        line=dict(color=color, width=6),
                        name=f'{corner_name} Damper ({length:.3f})',
                        showlegend=True
                    ))

                # Add centerline reference
                z_min = min([coords[k][2] for k in coords.keys()])
                z_max = max([coords['lf_upper'][2], coords['rf_upper'][2], coords['lr_upper'][2], coords['rr_upper'][2]])
                fig.add_trace(go.Scatter3d(
                    x=[0, 0],
                    y=[0, 0],
                    z=[z_min, z_max],
                    mode='lines',
                    line=dict(color='black', width=2, dash='dash'),
                    name='Centerline (Y=0)'
                ))

                # Update layout
                if using_multi_sheet:
                    title_text = f"3D Assembly: {selected_center} + Front: {selected_front_clip} + Rear: {selected_rear_clip}"
                else:
                    title_text = f"3D Assembly: {selected_center} + {selected_clip}"

                fig.update_layout(
                    scene=dict(
                        xaxis_title='X (Front-Back)',
                        yaxis_title='Y (Left-Right)',
                        zaxis_title='Z (Vertical)',
                        aspectmode='data',
                        camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))
                    ),
                    height=700,
                    showlegend=True,
                    title=title_text
                )

                st.plotly_chart(fig, use_container_width=True)

                # Display measurements
                st.markdown("---")
                st.subheader("📏 Damper Lengths")

                meas_cols = st.columns(4)

                def calc_length(p1, p2):
                    return np.sqrt(sum((p1[i] - p2[i])**2 for i in range(3)))

                with meas_cols[0]:
                    st.metric("LF Damper", f"{calc_length(coords['lf_upper'], lf_lower):.4f}")
                    st.caption(f"Upper: ({coords['lf_upper'][0]:.2f}, {coords['lf_upper'][1]:.2f}, {coords['lf_upper'][2]:.2f})")
                    st.caption(f"Lower: ({lf_lower[0]:.2f}, {lf_lower[1]:.2f}, {lf_lower[2]:.2f})")

                with meas_cols[1]:
                    st.metric("RF Damper", f"{calc_length(coords['rf_upper'], rf_lower):.4f}")
                    st.caption(f"Upper: ({coords['rf_upper'][0]:.2f}, {coords['rf_upper'][1]:.2f}, {coords['rf_upper'][2]:.2f})")
                    st.caption(f"Lower: ({rf_lower[0]:.2f}, {rf_lower[1]:.2f}, {rf_lower[2]:.2f})")

                with meas_cols[2]:
                    st.metric("LR Damper", f"{calc_length(coords['lr_upper'], lr_lower):.4f}")
                    st.caption(f"Upper: ({coords['lr_upper'][0]:.2f}, {coords['lr_upper'][1]:.2f}, {coords['lr_upper'][2]:.2f})")
                    st.caption(f"Lower: ({lr_lower[0]:.2f}, {lr_lower[1]:.2f}, {lr_lower[2]:.2f})")

                with meas_cols[3]:
                    st.metric("RR Damper", f"{calc_length(coords['rr_upper'], rr_lower):.4f}")
                    st.caption(f"Upper: ({coords['rr_upper'][0]:.2f}, {coords['rr_upper'][1]:.2f}, {coords['rr_upper'][2]:.2f})")
                    st.caption(f"Lower: ({rr_lower[0]:.2f}, {rr_lower[1]:.2f}, {rr_lower[2]:.2f})")

    else:
        # Show message when no data has been loaded yet in analysis tab
        st.info("⬅️ Please upload data and click 'Calculate' in the Data Configuration tab to view analysis results")
        st.markdown("""
        ### Once you've configured your data, you'll see:
        - **Reports & Tables**: Detailed analysis results, rankings, and comparison tables
        - **3D Assembly Visualizer**: Interactive 3D view of your suspension geometry
        - **Scatter Analysis**: Correlation plots and pattern identification
        """)
