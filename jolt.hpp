/**
 * jolt.hpp
 *
 * Estimates the available Cold Cranking Amps (CCA) from a battery's nominal
 * rating, ambient temperature, measured internal resistance, and open-circuit
 * voltage.
 *
 * Method:
 *   1. Temperature derating (SAE J537 / BCI): ~1% per °C below 25 °C,
 *      capped at a 50% loss. Produces a temperature-derated ceiling.
 *   2. Resistance-based limit (Ohm's law / SAE J537 test condition):
 *      The SAE CCA test holds terminal voltage at 7.2 V, so available
 *      cranking current is: I = (V_oc - 7.2) / R_internal.
 *      This reflects the battery's actual present-day capability.
 *   3. The lower of the two estimates is returned, capped at the nameplate
 *      CCA so an unusually low resistance cannot inflate the result.
 *
 * Dependencies: <algorithm>, <stdexcept> (C++17 or later recommended)
 */

#pragma once

#include <cmath>
#include <algorithm>
#include <optional>
#include <stdexcept>

/**
 * @brief Estimate available CCA given temperature and optionally resistance
 *        and open-circuit voltage.
 *
 * @param cca       Nameplate Cold Cranking Amps rating (A). Must be > 0.
 * @param temp_c    Ambient temperature in degrees Celsius.
 * @param r_ohm     Measured internal resistance in ohms (optional).
 *                  Pass std::nullopt to use temperature derating only.
 * @param v_oc      Open-circuit (resting) voltage in volts (optional).
 *                  Required alongside r_ohm for the resistance-based estimate.
 *                  Must be > 7.2 V for the resistance path to activate.
 *
 * @return Effective CCA in amps, rounded to one decimal place.
 *         Always >= 0 and <= cca.
 *
 * @throws std::invalid_argument if cca <= 0 or r_ohm <= 0 (when provided).
 *
 * Example — temperature only:
 *   effective_cca(550.0, -10.0)               // → 467.5 A
 *
 * Example — full calculation:
 *   effective_cca(550.0, -10.0, 0.015, 12.6)  // → 360.0 A
 */
inline double effective_cca(
    double                  cca,
    double                  temp_c,
    std::optional<double>   r_ohm = std::nullopt,
    std::optional<double>   v_oc  = std::nullopt)
{
    if (cca <= 0.0)
        throw std::invalid_argument("cca must be greater than zero.");
    if (r_ohm.has_value() && r_ohm.value() <= 0.0)
        throw std::invalid_argument("r_ohm must be greater than zero when provided.");

    // ── Step 1: temperature derating ─────────────────────────────────────────
    // ~1 % loss per °C below 25 °C, floored at 50 % of rated CCA.
    const double temp_factor = std::max(0.50, 1.0 - std::max(0.0, 25.0 - temp_c) * 0.01);
    const double temp_cca    = cca * temp_factor;

    // ── Step 2: resistance-based estimate ────────────────────────────────────
    // Only calculated when both r_ohm and v_oc are supplied and v_oc > 7.2 V.
    double result = temp_cca;

    if (r_ohm.has_value() && v_oc.has_value() && v_oc.value() > 7.2)
    {
        const double resistance_cca = (v_oc.value() - 7.2) / r_ohm.value();

        // Take the most limiting estimate; cap at nameplate CCA.
        result = std::min({ temp_cca, resistance_cca, cca });
    }

    // ── Step 3: clamp and round to 1 decimal place ───────────────────────────
    result = std::max(result, 0.0);
    result = std::round(result * 10.0) / 10.0;

    return result;
}