#<Filename>: <Jolt.py>
#<Author>:   <DANIEL DESAI>
#<Updated>:  <2026-03-03>
#<Version>:  <0.0.3>

# Requires `jolt_cli` (or `jolt_cli.exe` on Windows) to be on PATH or in the working directory


import math
import shutil
import subprocess
from pathlib import Path

import streamlit as st

# ── Constants ─────────────────────────────────────────────────────────────────
CLI_NAME   = 'jolt_cli'
CCA_MIN    = 50
CCA_MAX    = 1500
TEMP_C_MIN = -60
TEMP_C_MAX = 120

# ── Helpers ───────────────────────────────────────────────────────────────────

def find_cli() -> 'Path | None':
    local = Path(__file__).parent / CLI_NAME
    if local.exists():
        return local
    found = shutil.which(CLI_NAME)
    return Path(found) if found else None


def call_jolt(cca: float, temp_c: float,
              r_ohm: 'float | None', v_oc: 'float | None',
              agm: bool) -> dict:
    cli = find_cli()
    if cli is None:
        st.error(
            f'`{CLI_NAME}` not found. Build as:\n\n'
            '```\ng++ -std=c++17 -O2 -o jolt_cli jolt_cli.cpp\n```'
        )
        st.stop()

    args = [str(cli), str(cca), str(temp_c)]
    if r_ohm is not None and v_oc is not None:
        args += [str(r_ohm), str(v_oc)]
    if agm:
        args.append('--agm')

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=5)
    except subprocess.TimeoutExpired:
        st.error('jolt_cli timed out.')
        st.stop()

    if proc.returncode == 2:
        st.error(f'Validation error from jolt_cli: {proc.stderr.strip()}')
        st.stop()
    if proc.returncode != 0:
        st.error(f'jolt_cli failed (exit {proc.returncode}): {proc.stderr.strip()}')
        st.stop()

    lines = proc.stdout.strip().splitlines()
    res_raw = float(lines[3])

    return {
        'effective_cca':  float(lines[0]),
        'temp_factor':    float(lines[1]),
        'temp_cca':       float(lines[2]),
        'resistance_cca': res_raw if res_raw >= 0 else None,
        'limiting_stage': lines[4].strip(),
    }


def gauge_color(pct: float) -> str:
    if pct >= 0.75: return 'green'
    if pct >= 0.50: return 'orange'
    return 'red'


def gauge_label(pct: float) -> str:
    if pct >= 0.75: return 'Good'
    if pct >= 0.50: return 'Marginal'
    return 'Poor'


def build_warnings(r: dict, cca: float, v_oc: 'float | None',
                   charge_v: 'float | None', ecu_v: 'float | None',
                   agm: bool) -> list:
    warns = []
    pct   = r['effective_cca'] / cca
    stage = r['limiting_stage']

    if pct < 0.50:
        warns.append('**Critical:** Available CCA is below 50 % of rated capacity. '
                     'Battery replacement strongly recommended.')
    elif pct < 0.75:
        warns.append('**Warning:** Available CCA is below 75 % of rated capacity. '
                     'Monitor closely; consider replacement before winter.')

    if stage == 'resistance':
        warns.append('**Limiting factor — internal resistance:** Resistance is the '
                     'primary constraint on cranking performance, not temperature. '
                     'This often indicates sulfation or aging.')
    elif stage == 'temperature':
        rate = '0.5 % per °C (AGM)' if agm else '1.0 % per °C (flooded)'
        warns.append(f'**Limiting factor — temperature:** Cold ambient conditions are '
                     f'the primary constraint, derated at {rate}.')
    elif stage == 'nameplate':
        warns.append('**Limiting factor — rated CCA:** Estimated cranking current '
                     'exceeds the rated CCA; result is capped at the rated value.')

    if v_oc is not None:
        if v_oc < 12.0:
            warns.append('**Low open-circuit voltage:** < 12.0 V suggests the battery '
                         'is significantly discharged or has a shorted cell.')
        elif v_oc < 12.4:
            warns.append('**Low open-circuit voltage:** 12.0–12.4 V indicates a '
                         'partially discharged state. Charge before testing.')

    if charge_v is not None and charge_v > 15.0:
        warns.append('**High charging voltage:** > 15.0 V may indicate a faulty '
                     'alternator regulator.')

    if ecu_v is not None and charge_v is not None and (charge_v - ecu_v) > 1.0:
        warns.append(
            f'**Voltage discrepancy:** ECU-reported voltage ({ecu_v:.2f} V) is more than '
            f'1 V below the alternator/charging voltage ({charge_v:.2f} V). '
            'This may indicate a wiring resistance issue, a failing ground, or an inaccurate ECU sensor.'
        )

    if ecu_v is not None and ecu_v < 9.6:
        warns.append('**Low ECU voltage during crank:** < 9.6 V may trigger ECU '
                     'resets or failed start attempts.')

    return warns


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title='Jolt', page_icon='🔋', layout='wide')

st.markdown('''
<style>
button[data-testid="stNumberInputStepDown"],
button[data-testid="stNumberInputStepUp"] {
    display: none;
}
</style>
''', unsafe_allow_html=True)

# ── Two-column layout ─────────────────────────────────────────────────────────
left_col, right_col = st.columns([1, 1], gap='large')

with left_col:
    # ── Methodology banner ────────────────────────────────────────────────────
    st.info(
        '**Methodology:** Temperature derating follows SAE J537 / BCI — ~1 % per °C '
        'below 25 °C for flooded batteries, ~0.5 % per °C for AGM, floored at 50 % of '
        'rated CCA. When internal resistance and open-circuit voltage are provided, a '
        'resistance-based estimate is also calculated using Ohm\'s law at the 7.2 V SAE '
        'test threshold. The lower of the two estimates is returned, capped at rated CCA.',
    )

    # ── Input form ────────────────────────────────────────────────────────────
    with st.form('inputs'):
        st.write(':blue[Battery Parameters]')
        col11, col12, col13, col14 = st.columns(4)

        with col11:
            cca = st.number_input(
                'Rated CCA (A)', min_value=CCA_MIN, max_value=CCA_MAX,
                value=None, step=10,
                help='Rated Cold Cranking Amps from the battery label.'
            )
            is_agm = st.checkbox('AGM battery', value=False,
                                 help='AGM batteries derate at ~0.5 % per °C below 25 °C '
                                      '(vs ~1 % for flooded), per BCI industry data.')

        with col12:
            temp_c_input = st.number_input(
                'Air Temperature',
                min_value=TEMP_C_MIN, max_value=TEMP_C_MAX,
                value=20, step=1,
                help='Air temperature at time of measurement.'
            )
            temp_unit = st.segmented_control(
                'Unit', options=['°C', '°F'], default='°C', label_visibility='collapsed'
            )

        # Convert to °C for the CLI
        if temp_unit == '°F':
            temp_c = (temp_c_input - 32) * 5 / 9
            temp_c = max(TEMP_C_MIN, min(TEMP_C_MAX, temp_c))
        else:
            temp_c = temp_c_input

        st.write(':blue[Electrical Measurements]')
        col3, col4, col5, col6 = st.columns(4)

        with col3:
            v_oc = st.number_input(
                'Resting Voltage (V)',
                min_value=0.0, max_value=16.0,
                value=None, step=0.1,
                help='Measured after the battery has rested ≥ 2 hours with no load.'
            )
        with col4:
            r_ohm = st.number_input(
                'Resistance (mΩ)',
                min_value=0.0, max_value=500.0,
                value=None, step=0.5,
                help='As measured by a conductance/impedance tester.'
            )
        with col5:
            charge_v = st.number_input(
                'Alternator Voltage (V)',
                min_value=0.0, max_value=20.0,
                value=None, step=0.1,
                help='Voltage measured at battery terminals with engine running.'
            )
        with col6:
            ecu_v = st.number_input(
                'OBD2 Voltage (V)',
                min_value=0.0, max_value=20.0,
                value=None, step=0.1,
                help='Battery voltage as reported by the ECU via OBD2.'
            )

        submitted = st.form_submit_button('⚡ Estimate CCA', use_container_width=True)

# ── On submit ─────────────────────────────────────────────────────────────────
if submitted:
    if not cca:
        with left_col:
            st.error('Please enter a Rated CCA value.')
        st.stop()

    r_ohm_val = (r_ohm / 1000.0) if (r_ohm and r_ohm > 0 and v_oc and v_oc > 0) else None
    v_oc_val  = v_oc              if (r_ohm and r_ohm > 0 and v_oc and v_oc > 0) else None

    st.session_state['charge_v'] = charge_v
    st.session_state['ecu_v']    = ecu_v

    result = call_jolt(cca, temp_c, r_ohm_val, v_oc_val, is_agm)

    eff   = result['effective_cca']
    pct   = eff / cca
    color = gauge_color(pct)
    label = gauge_label(pct)

    with right_col:
        # ── Gauge ──────────────────────────────────────────────────────────
        st.subheader('Result')

        gauge_col, metric_col = st.columns([2, 1])
        with gauge_col:
            sweep = min(pct, 1.0) * 180
            end_x = 100 + 80 * math.cos(math.radians(180 - sweep))
            end_y = 100 - 80 * math.sin(math.radians(180 - sweep))
            large = 1 if sweep > 180 else 0
            st.markdown(f'''
            <svg viewBox="0 0 200 110" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:320px">
              <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#e0e0e0" stroke-width="18" stroke-linecap="round"/>
              <path d="M 20 100 A 80 80 0 {large} 1 {end_x:.2f} {end_y:.2f}"
                    fill="none" stroke="{color}" stroke-width="18" stroke-linecap="round"/>
              <text x="100" y="88" text-anchor="middle" font-size="26" font-weight="bold" fill="{color}">{eff:.1f}</text>
              <text x="100" y="105" text-anchor="middle" font-size="11" fill="#888">CCA available</text>
            </svg>
            ''', unsafe_allow_html=True)

        with metric_col:
            st.metric('Available CCA', f'{eff:.1f} A')
            st.metric('Rated CCA',     f'{cca:.0f} A')
            st.metric('Efficiency',    f'{pct*100:.1f} %')
            st.markdown(f'**Health: :{color}[{label}]**')

        # ── Diagnostics ────────────────────────────────────────────────────
        warns = build_warnings(result, cca, v_oc_val, charge_v, ecu_v, is_agm)
        st.subheader('Diagnostics')
        if warns:
            for w in warns:
                st.markdown(w)
        else:
            st.success('No issues detected. Battery appears to be in good health.')