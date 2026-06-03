from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib.pyplot as plt
import pandas as pd

# Diccionario de complejidad mantenible y reutilizable en todos los flujos.
DEFAULT_COMPLEXITY_BY_LOCATION = {
    "ORL": 1.0,
    "Pulmon": 1.0,
    "Prostata3N": 1.0,
    "Prostata2N y 1N": 0.6,
    "Mama": 0.8,
    "Sarcoma": 1.0,
    "Recto": 1.0,
    "Digestivo": 1.0,
    "Linfoma": 1.0,
    "Cerebral": 1.0,
    "Electrones": 0.5,
    "Piel": 0.5,
    "SBRT/SRS": 1.4,
    "Ginecolog": 1.0,
    "Benigna": 0.5,
    "Otros": 1.0,
    "Paliativo": 0.5,
}

# Mapeo nombre->codigo para enlazar actividad y disponibilidad de cada fisico.
DEFAULT_PHYSICIST_CODE_BY_NAME = {
    "Alfonso": "AL",
    "César": "CR",
    "Guadalupe": "GM",
    "Carmen": "CC",
    "Pilar": "PJ",
    "Felipe": "FO",
    "Juan": "JC",
    "Juanma": "JP",
}

DEFAULT_MARKERS = ["o", "D", "v", "^", "<", ">", "p", "*", "X", "s"]


def load_availability_data(availability_file: str | Path) -> pd.DataFrame:
    """Carga disponibilidad de fisicos y normaliza tipos de datos."""
    availability_df = pd.read_excel(availability_file)
    availability_df = availability_df.rename(
        columns={
            "Physicist": "physicist",
            "Date": "date",
            "Availability": "availability",
        }
    )
    required_columns = {"physicist", "date", "availability"}
    missing_columns = required_columns.difference(availability_df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Faltan columnas en disponibilidad: {missing}")

    availability_df = availability_df.copy()
    availability_df["date"] = pd.to_datetime(availability_df["date"])
    availability_df["availability"] = pd.to_numeric(availability_df["availability"], errors="coerce").fillna(0.0)
    return availability_df


def load_assignments_data(
    assignments_file: str | Path,
    *,
    usecols: Sequence[int] | None = tuple(range(0, 18)),
    skip_rows: int = 11,
    date_column: str = "Fecha",
) -> pd.DataFrame:
    """Carga la tabla de reparto y rellena la fecha ausente de filas consecutivas."""
    assignments_df = pd.read_excel(assignments_file, usecols=usecols, skiprows=skip_rows)
    if date_column not in assignments_df.columns:
        raise ValueError(f"No existe la columna de fecha '{date_column}' en el reparto")

    assignments_df = assignments_df.copy()
    assignments_df[date_column] = pd.to_datetime(assignments_df[date_column]).ffill()
    assignments_df = assignments_df.dropna(subset=[date_column])
    return assignments_df


def load_physicists_from_assignments(
    assignments_file: str | Path,
    *,
    usecols: Sequence[int] = (0, 19),
    nrows: int = 8,
    physicist_column_name: str = "Physicist",
) -> list[str]:
    """Extrae la lista de fisicos desde la cabecera resumen del Excel de reparto."""
    physicists_df = pd.read_excel(assignments_file, usecols=usecols, nrows=nrows)
    physicists_df.columns = [physicist_column_name, "plans"]
    physicists = (
        physicists_df[physicist_column_name]
        .dropna()
        .astype(str)
        .str.strip()
        .drop_duplicates()
        .tolist()
    )
    return physicists


def business_days_between(start_date: pd.Timestamp, end_date: pd.Timestamp) -> int:
    """Numero de dias laborables entre start_date (incluido) y end_date (excluido)."""
    if end_date <= start_date:
        return 0
    return pd.bdate_range(start_date, end_date - pd.Timedelta(days=1)).size


def _build_cumulative_activity_by_physicist(
    assignments_df: pd.DataFrame,
    physicists: Sequence[str],
    *,
    location: str | None,
    apply_complexity: bool,
    complexity_by_location: Mapping[str, float],
    date_column: str,
) -> pd.DataFrame:
    """Calcula actividad acumulada por fisico y fecha."""
    long_df = assignments_df.melt(
        id_vars=[date_column],
        var_name="location",
        value_name="physicist",
    )
    long_df = long_df.dropna(subset=["physicist"]).copy()
    long_df["physicist"] = long_df["physicist"].astype(str).str.strip()

    if location is not None:
        long_df = long_df[long_df["location"] == location]

    if apply_complexity:
        long_df["weight"] = long_df["location"].map(complexity_by_location).fillna(1.0)
    else:
        long_df["weight"] = 1.0

    daily_activity = (
        long_df.groupby([date_column, "physicist"], dropna=False)["weight"]
        .sum()
        .unstack(fill_value=0.0)
    )

    if daily_activity.empty:
        return pd.DataFrame(columns=physicists)

    daily_activity.index = pd.to_datetime(daily_activity.index)
    date_range = pd.date_range(daily_activity.index.min(), daily_activity.index.max(), freq="D")
    daily_activity = daily_activity.reindex(date_range, fill_value=0.0)
    daily_activity = daily_activity.reindex(columns=list(physicists), fill_value=0.0)

    cumulative_activity = daily_activity.cumsum()
    cumulative_activity.index.name = date_column
    return cumulative_activity


def _build_cumulative_availability_by_physicist(
    availability_df: pd.DataFrame,
    dates: pd.DatetimeIndex,
    physicists: Sequence[str],
    physicist_code_by_name: Mapping[str, str],
) -> pd.DataFrame:
    """Calcula disponibilidad acumulada por fisico en fechas de evaluacion."""
    cumulative_availability_df = pd.DataFrame(index=dates)

    if dates.empty:
        return cumulative_availability_df

    full_date_range = pd.date_range(dates.min(), dates.max(), freq="D")
    business_day_mask = (full_date_range.dayofweek < 5).astype(float)

    for physicist_name in physicists:
        physicist_code = physicist_code_by_name.get(physicist_name)
        if physicist_code is None:
            cumulative_availability_df[f"av_{physicist_name}"] = 0.0
            continue

        physicist_availability = availability_df[
            availability_df["physicist"].astype(str).str.strip() == physicist_code
        ][["date", "availability"]].sort_values("date")

        if physicist_availability.empty:
            cumulative_availability_df[f"av_{physicist_name}"] = 0.0
            continue

        physicist_availability = physicist_availability.drop_duplicates(subset=["date"], keep="last")
        availability_series = physicist_availability.set_index("date")["availability"].astype(float)

        previous_changes = availability_series[availability_series.index <= full_date_range.min()]
        initial_availability = float(previous_changes.iloc[-1]) if not previous_changes.empty else 0.0

        daily_availability = pd.Series(index=full_date_range, dtype=float)
        daily_availability.iloc[0] = initial_availability
        daily_availability.update(availability_series[availability_series.index >= full_date_range.min()])
        daily_availability = daily_availability.ffill().fillna(initial_availability)

        daily_weighted_availability = daily_availability * business_day_mask
        cumulative_series = daily_weighted_availability.cumsum()
        cumulative_availability_df[f"av_{physicist_name}"] = cumulative_series.reindex(dates).to_numpy()

    return cumulative_availability_df


def add_physicist_norm_activity(activity_df: pd.DataFrame, physicists: Sequence[str]) -> pd.DataFrame:
    """Anade columnas nac_<fisico> = actividad acumulada / disponibilidad acumulada."""
    for physicist_name in physicists:
        activity_column = physicist_name
        availability_column = f"av_{physicist_name}"
        normalized_column = f"nac_{physicist_name}"

        denominator = activity_df[availability_column].replace(0, pd.NA)
        activity_df[normalized_column] = activity_df[activity_column].div(denominator)

    return activity_df


def create_physicist_activities(
    assignments_df: pd.DataFrame,
    physicists: Sequence[str],
    *,
    availability_df: pd.DataFrame,
    physicist_code_by_name: Mapping[str, str] | None = None,
    complexity_by_location: Mapping[str, float] | None = None,
    location: str | None = None,
    complexity: bool = False,
    date_column: str = "Fecha",
) -> pd.DataFrame:
    """
    Genera dataframe acumulado con actividad, disponibilidad y actividad normalizada.

    Salida:
    - Columnas por fisico: actividad acumulada.
    - Columnas av_<fisico>: disponibilidad acumulada.
    - Columnas nac_<fisico>: actividad acumulada normalizada por disponibilidad.
    """
    resolved_codes = physicist_code_by_name or DEFAULT_PHYSICIST_CODE_BY_NAME
    resolved_complexity = complexity_by_location or DEFAULT_COMPLEXITY_BY_LOCATION

    cumulative_activity_df = _build_cumulative_activity_by_physicist(
        assignments_df,
        physicists,
        location=location,
        apply_complexity=complexity,
        complexity_by_location=resolved_complexity,
        date_column=date_column,
    )

    cumulative_availability_df = _build_cumulative_availability_by_physicist(
        availability_df,
        cumulative_activity_df.index,
        physicists,
        resolved_codes,
    )

    result_df = cumulative_activity_df.copy()
    result_df = result_df.join(cumulative_availability_df, how="left")
    result_df = add_physicist_norm_activity(result_df, physicists)
    return result_df


def build_activity_dataframe_from_files(
    assignments_file: str | Path,
    availability_file: str | Path,
    *,
    skip_rows: int = 11,
    assignment_usecols: Sequence[int] | None = tuple(range(0, 18)),
    physicists_usecols: Sequence[int] = (0, 19),
    physicists_nrows: int = 8,
    location: str | None = None,
    complexity: bool = False,
    date_column: str = "Fecha",
    physicist_code_by_name: Mapping[str, str] | None = None,
    complexity_by_location: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Flujo completo para generar el dataframe de informe a partir de los Excel."""
    assignments_df = load_assignments_data(
        assignments_file,
        usecols=assignment_usecols,
        skip_rows=skip_rows,
        date_column=date_column,
    )
    availability_df = load_availability_data(availability_file)
    physicists = load_physicists_from_assignments(
        assignments_file,
        usecols=physicists_usecols,
        nrows=physicists_nrows,
    )

    return create_physicist_activities(
        assignments_df=assignments_df,
        physicists=physicists,
        availability_df=availability_df,
        physicist_code_by_name=physicist_code_by_name,
        complexity_by_location=complexity_by_location,
        location=location,
        complexity=complexity,
        date_column=date_column,
    )


def plot_normalized_activity(
    activity_df: pd.DataFrame,
    physicists: Sequence[str],
    *,
    location: str | None = None,
    figsize: tuple[int, int] = (12, 6),
    markers: Sequence[str] | None = None,
    markevery: int = 5,
    ax: plt.Axes | None = None,
) -> tuple[plt.Figure, plt.Axes]:
    """Genera el grafico de evolucion temporal de nac_<fisico>."""
    resolved_markers = list(markers) if markers is not None else DEFAULT_MARKERS

    if ax is None:
        figure, axis = plt.subplots(figsize=figsize)
    else:
        axis = ax
        figure = axis.figure

    if location:
        axis.set_title(f"Actividad acumulada normalizada por Fisico para la localizacion {location}")
    else:
        axis.set_title("Actividad acumulada normalizada por Fisico para todas las localizaciones")

    for index, physicist_name in enumerate(physicists):
        column_name = f"nac_{physicist_name}"
        if column_name not in activity_df.columns:
            continue

        series = pd.to_numeric(activity_df[column_name], errors="coerce")

        if series.notna().any():
            series.plot(
                ax=axis,
                marker=resolved_markers[index % len(resolved_markers)],
                markevery=markevery,
                label=DEFAULT_PHYSICIST_CODE_BY_NAME[physicist_name],
            )
    axis.set_xlabel("Fecha")
    axis.set_ylabel("Actividad acumulada normalizada")
    axis.grid(True, alpha=0.3)
    axis.legend()
    return figure, axis