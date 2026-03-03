/**
 * 
 * <Filename>: <jolt_cli.cpp>
 * <Author>:   <DANIEL DESAI>
 * <Updated>:  <2026-03-03>
 * <Version>:  <0.0.1>
 *
 * CLI wrapper around jolt.hpp for use as a subprocess from Python/Streamlit.
 *
 * Usage:
 *   jolt_cli <cca> <temp_c> [<r_ohm> <v_oc>] [--agm]
 *
 *   --agm flag can appear anywhere after the positional args.
 *
 * AGM derating:
 *   AGM batteries derate at ~0.5% per °C below 25°C (vs ~1% for flooded).
 *   This is consistent with BCI/industry data showing AGM retains ~85% CCA
 *   at -20°F vs ~65% for flooded. SAE J537 does not define a separate curve;
 *   the nameplate CCA already reflects chemistry — this adjustment accounts
 *   for the improved thermal resilience of AGM in field estimation.
 *
 * Output (stdout, one value per line):
 *   Line 0: effective_cca          (double)
 *   Line 1: temp_factor            (double, 0.50–1.00)
 *   Line 2: temp_cca               (double)
 *   Line 3: resistance_cca         (double, or -1 if not calculated)
 *   Line 4: limiting_stage         (string: "temperature"|"resistance"|"nameplate")
 *
 * Exit codes:
 *   0 — success
 *   1 — bad argument count / parse failure
 *   2 — invalid argument value
 *
 * Build (C++17 or later):
 *   g++ -std=c++17 -O2 -o jolt_cli jolt_cli.cpp
 */

#include "jolt.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char* argv[])
{
    // ── Parse flags ───────────────────────────────────────────────────────────
    auto agm = false;
    auto pos  = std::vector<std::string>{};

    for (int k = 1; k < argc; ++k) {
        auto a = std::string(argv[k]);
        if (a == "--agm") agm = true;
        else              pos.push_back(a);
    }

    if (pos.size() != 2 && pos.size() != 4) {
        std::cerr << "Usage: jolt_cli <cca> <temp_c> [<r_ohm> <v_oc>] [--agm]\n";
        return 1;
    }

    double cca, temp_c;
    auto r_ohm = std::optional<double>{};
    auto v_oc  = std::optional<double>{};

    try {
        cca    = std::stod(pos[0]);
        temp_c = std::stod(pos[1]);
        if (pos.size() == 4) {
            r_ohm = std::stod(pos[2]);
            v_oc  = std::stod(pos[3]);
        }
    } catch (...) {
        std::cerr << "Error: could not parse numeric arguments.\n";
        return 1;
    }

    // Validate inputs
    if (cca <= 0.0) {
        std::cerr << "Error: cca must be greater than zero.\n";
        return 2;
    }
    if (r_ohm.has_value() && r_ohm.value() <= 0.0) {
        std::cerr << "Error: r_ohm must be greater than zero when provided.\n";
        return 2;
    }

    // ── Temperature derating ─────────────────────────────────────────────────
    // Flooded: ~1.0% per °C below 25°C  (jolt.hpp default)
    // AGM:     ~0.5% per °C below 25°C  (BCI industry data)
    // Both floored at 50% of nameplate CCA.
    auto derate_rate = agm ? 0.005 : 0.01;
    auto temp_factor = std::max(0.50, 1.0 - std::max(0.0, 25.0 - temp_c) * derate_rate);
    auto temp_cca    = cca * temp_factor;

    // ── Resistance-based estimate ─────────────────────────────────────────────
    auto resistance_cca = -1.0;   // sentinel: -1 means not calculated
    if (r_ohm.has_value() && v_oc.has_value() && v_oc.value() > 7.2)
        resistance_cca = (v_oc.value() - 7.2) / r_ohm.value();

    // ── Effective CCA: most limiting of temp, resistance, nameplate ───────────
    auto effective = temp_cca;
    if (resistance_cca >= 0.0)
        effective = std::min({ temp_cca, resistance_cca, cca });
    effective = std::max(effective, 0.0);
    effective = std::round(effective * 10.0) / 10.0;

    // ── Determine limiting stage ──────────────────────────────────────────────
    auto limiting = std::string("temperature");
    if (resistance_cca >= 0.0) {
        auto r_r = std::round(resistance_cca * 10.0) / 10.0;
        auto r_t = std::round(temp_cca        * 10.0) / 10.0;
        if (effective >= cca) limiting = "nameplate";
        else if (r_r < r_t)   limiting = "resistance";
    }

    std::cout << std::fixed;
    std::cout.precision(1);
    std::cout << effective       << "\n"   // line 0
              << temp_factor     << "\n"   // line 1
              << temp_cca        << "\n"   // line 2
              << resistance_cca  << "\n"   // line 3
              << limiting        << "\n";  // line 4

    return 0;
}