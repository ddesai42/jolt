# Jolt

For estimating the available Cold Cranking Amps (CCA) of a car battery based on temperature, internal resistance, and open-circuit voltage.

---

## Methodology

Temperature derating follows **SAE J537 / BCI** industry standards:

- **Flooded batteries:** ~1.0 % per °C below 25 °C
- **AGM batteries:** ~0.5 % per °C below 25 °C
- Derating is floored at 50 % of rated CCA

When internal resistance and open-circuit voltage are both provided, a second estimate is calculated using **Ohm's law at the 7.2 V SAE cranking threshold**. The lower of the two estimates is returned, capped at the rated CCA.

---

## Architecture

Jolt is made up of three files:

- **`jolt.hpp`** — header-only C++ library that implements the core `effective_cca()` function. Can be included in any C++17 project independently of the CLI or the Streamlit app.
- **`jolt_cli.cpp`** — thin CLI wrapper around `jolt.hpp`, compiled to a binary that `Jolt.py` calls as a subprocess.
- **`Jolt.py`** — Streamlit front-end that collects inputs, invokes `jolt_cli`, and displays results.

---

## Requirements

### Python dependencies

```
streamlit
```

Install with:

```bash
pip install streamlit
```

### CLI backend

Jolt requires the `jolt_cli` binary (compiled from `jolt_cli.cpp`) to be either:

- in the same directory as `Jolt.py`, or
- on your system `PATH`

Build the CLI with:

```bash
g++ -std=c++17 -O2 -o jolt_cli jolt_cli.cpp
```

On Windows the binary should be named `jolt_cli.exe`.

---

## Running the App

```bash
streamlit run Jolt.py
```

---

## Inputs

### Battery Parameters

| Field | Description |
|---|---|
| Rated CCA (A) | Cold Cranking Amps from the battery label (50–1500 A) |
| AGM battery | Check if the battery is AGM; affects the temperature derating rate |
| Air Temperature | Ambient air temperature at time of measurement (°C or °F) |

### Electrical Measurements

| Field | Description |
|---|---|
| Resting Voltage (V) | Open-circuit voltage after ≥ 2 hours of rest with no load |
| Resistance (mΩ) | Internal resistance as measured by a conductance/impedance tester |
| Alternator Voltage (V) | Voltage at battery terminals with engine running |
| OBD2 Voltage (V) | Battery voltage as reported by the ECU via OBD2 |

Resting voltage and resistance are both required to enable the resistance-based CCA estimate. Alternator voltage and OBD2 voltage are used only for diagnostic warnings.

---

## Outputs

### Result

- **Available CCA** — estimated cranking amps under current conditions
- **Efficiency** — available CCA as a percentage of rated CCA
- **Health** — Good (≥ 75 %), Marginal (50–74 %), or Poor (< 50 %)

### Diagnostics

Warnings are generated for the following conditions:

- Available CCA below 75 % or 50 % of rated capacity
- Internal resistance identified as the limiting factor (may indicate sulfation or aging)
- Temperature identified as the limiting factor
- Open-circuit voltage below 12.4 V (discharged) or 12.0 V (critically low / shorted cell)
- Alternator voltage above 15.0 V (possible faulty regulator)
- More than 1 V difference between alternator voltage and OBD2-reported voltage (possible wiring or ground issue)
- OBD2 voltage below 9.6 V during cranking (may trigger ECU resets)

---

## File Structure

```
.
├── Jolt.py          # Streamlit front-end
├── jolt.hpp         # Header-only core estimation library
├── jolt_cli.cpp     # CLI wrapper around jolt.hpp (compile before use)
├── jolt_cli         # Compiled binary (Linux/macOS)
└── README.md
```

