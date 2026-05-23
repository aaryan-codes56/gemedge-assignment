"""
Procurement Intelligence Report Generator
==========================================
Inherits BaseInsightsGenerator. Transforms cleaned datasets into:
  - Vendor intelligence (win rates, participation, anomalies)
  - Ministry / department analytics
  - Pricing spread analytics
  - Anomaly risk report
  - Category-level intelligence
  - HTML dashboard
  - Executive summary (Markdown)
"""

from __future__ import annotations

import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from src.core.base import BaseInsightsGenerator
from src.utils.file_utils import save_json, save_csv
from src.utils.logger import get_logger

logger = get_logger("procurement_report_generator")

ISO_NOW = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ── helpers ────────────────────────────────────────────────────────────────────

def _safe_pct(num: float, denom: float, precision: int = 1) -> float:
    return round(num / denom * 100, precision) if denom else 0.0


def _top_n(series: pd.Series, n: int = 10) -> Dict[str, int]:
    return series.value_counts().head(n).to_dict()


def _round_dict(d: Dict[str, Any], p: int = 2) -> Dict[str, Any]:
    return {k: round(v, p) if isinstance(v, float) else v for k, v in d.items()}


# ── main class ─────────────────────────────────────────────────────────────────

class ProcurementReportGenerator(BaseInsightsGenerator):
    """End-to-end procurement intelligence analytics engine."""

    def __init__(self, output_dir: Path = Path("outputs")) -> None:
        super().__init__()
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC — BaseInsightsGenerator interface
    # ═══════════════════════════════════════════════════════════════════════

    def generate_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Alias: generate listing-level summary for BaseScraper compatibility."""
        return self._summary_statistics(df, df, df)

    def validate(self, report: Dict[str, Any]) -> bool:
        required = ["generated_at", "summary"]
        missing = [k for k in required if k not in report]
        if missing:
            self.logger.warning(f"Report validation: missing keys {missing}")
            return False
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC — full pipeline
    # ═══════════════════════════════════════════════════════════════════════

    def run_full_pipeline(
        self,
        listings_df: pd.DataFrame,
        results_df: pd.DataFrame,
        vendors_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Runs all analytics modules, persists every report, and returns a
        master report dictionary.
        """
        self.logger.info("Starting procurement intelligence reporting pipeline...")

        summary   = self._summary_statistics(listings_df, results_df, vendors_df)
        vendor    = self._vendor_intelligence(vendors_df)
        ministry  = self._ministry_intelligence(listings_df, vendors_df)
        pricing   = self._pricing_intelligence(vendors_df)
        anomalies = self._anomaly_report(vendors_df)
        category  = self._category_intelligence(listings_df, vendors_df)

        master = {
            "generated_at":  ISO_NOW,
            "summary":       summary,
            "vendor":        vendor,
            "ministry":      ministry,
            "pricing":       pricing,
            "anomalies":     anomalies,
            "category":      category,
        }

        self._persist_all(master, listings_df, vendors_df, anomalies, category)
        self._generate_html_dashboard(master)
        self._generate_executive_summary(master)

        self.logger.info("Reporting pipeline complete.")
        return master

    # ═══════════════════════════════════════════════════════════════════════
    # ANALYTICS MODULES
    # ═══════════════════════════════════════════════════════════════════════

    def _summary_statistics(
        self,
        listings_df: pd.DataFrame,
        results_df: pd.DataFrame,
        vendors_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        total_bids     = len(listings_df)
        total_results  = len(results_df)
        total_vendors  = int(vendors_df["vendor_name"].nunique()) if not vendors_df.empty and "vendor_name" in vendors_df.columns else 0
        total_vendor_rows = len(vendors_df)

        awarded = 0
        if not vendors_df.empty and "awarded_flag" in vendors_df.columns:
            awarded = int(vendors_df["awarded_flag"].sum())

        return {
            "total_bids_analyzed":         total_bids,
            "total_results_available":     total_results,
            "total_unique_vendors":        total_vendors,
            "total_vendor_evaluation_rows":total_vendor_rows,
            "total_awarded_contracts":     awarded,
        }

    def _vendor_intelligence(self, vendors_df: pd.DataFrame) -> Dict[str, Any]:
        if vendors_df.empty or "vendor_name" not in vendors_df.columns:
            return {"note": "No vendor evaluation data available."}

        participation = _top_n(vendors_df["vendor_name"], 15)

        winners = vendors_df[vendors_df.get("awarded_flag", pd.Series(dtype=bool))]
        win_counts = _top_n(winners["vendor_name"], 15) if not winners.empty else {}

        # Win rate per vendor
        total_per_vendor = vendors_df["vendor_name"].value_counts()
        wins_per_vendor  = winners["vendor_name"].value_counts() if not winners.empty else pd.Series(dtype=int)
        win_rates = {}
        for vendor, wins in wins_per_vendor.items():
            total = total_per_vendor.get(vendor, 0)
            win_rates[str(vendor)] = _safe_pct(wins, total)

        # Average awarded value
        avg_awarded = None
        if "quoted_price" in vendors_df.columns and not winners.empty:
            avg_awarded = round(float(winners["quoted_price"].mean()), 2)

        # Anomaly frequency per vendor
        anomaly_cols = [c for c in vendors_df.columns if c.startswith("anomaly_")]
        anomaly_freq: Dict[str, int] = {}
        if anomaly_cols:
            for col in anomaly_cols:
                flagged = vendors_df[vendors_df[col]]["vendor_name"].value_counts()
                for v, cnt in flagged.items():
                    anomaly_freq[str(v)] = anomaly_freq.get(str(v), 0) + int(cnt)

        return {
            "top_vendors_by_participation": participation,
            "top_winning_vendors":          win_counts,
            "vendor_win_rates_pct":         win_rates,
            "average_awarded_value_inr":    avg_awarded,
            "vendors_with_anomaly_flags":   dict(sorted(anomaly_freq.items(), key=lambda x: -x[1])[:10]),
        }

    def _ministry_intelligence(
        self, listings_df: pd.DataFrame, vendors_df: pd.DataFrame
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if not listings_df.empty and "ministry" in listings_df.columns:
            result["top_ministries_by_bid_count"] = _top_n(listings_df["ministry"].dropna(), 10)

        if not listings_df.empty and "department" in listings_df.columns:
            result["top_departments_by_bid_count"] = _top_n(listings_df["department"].dropna(), 10)

        # Average vendors per bid (competition intensity) — from vendor eval
        if not vendors_df.empty and "bid_id" in vendors_df.columns:
            fin_q = vendors_df[vendors_df.get("financially_qualified", pd.Series(dtype=bool))]
            if not fin_q.empty:
                competition = fin_q.groupby("bid_id")["vendor_name"].count()
                result["avg_competition_per_bid"] = round(float(competition.mean()), 2)
                result["max_competition_per_bid"] = int(competition.max())
                result["min_competition_per_bid"] = int(competition.min())

        # Procurement concentration: % of bids from top ministry
        if not listings_df.empty and "ministry" in listings_df.columns:
            vc = listings_df["ministry"].dropna().value_counts()
            if not vc.empty:
                top_share = _safe_pct(vc.iloc[0], vc.sum())
                result["top_ministry_concentration_pct"] = top_share

        return result

    def _pricing_intelligence(self, vendors_df: pd.DataFrame) -> Dict[str, Any]:
        if vendors_df.empty or "quoted_price" not in vendors_df.columns:
            return {"note": "No pricing data available."}

        fin = vendors_df[
            (vendors_df.get("financially_qualified", pd.Series(dtype=bool))) &
            (vendors_df["quoted_price"] > 0)
        ]

        if fin.empty:
            return {"note": "No financially-qualified vendor pricing data."}

        avg_spread = 0.0
        if "price_spread_pct" in vendors_df.columns:
            spreads = vendors_df["price_spread_pct"].dropna()
            avg_spread = round(float(spreads.mean()), 2) if not spreads.empty else 0.0

        avg_l1_l2_gap = 0.0
        if "l1_vs_vendor_pct" in vendors_df.columns:
            l2_rows = vendors_df[vendors_df.get("vendor_rank", "") == "L2"]["l1_vs_vendor_pct"].dropna()
            avg_l1_l2_gap = round(float(l2_rows.mean()), 2) if not l2_rows.empty else 0.0

        avg_price   = round(float(fin["quoted_price"].mean()), 2)
        max_price   = round(float(fin["quoted_price"].max()), 2)
        min_price   = round(float(fin["quoted_price"].min()), 2)

        # Abnormal spreads (>100%)
        abnormal_count = 0
        if "anomaly_abnormal_spread" in vendors_df.columns:
            abnormal_count = int(vendors_df["anomaly_abnormal_spread"].sum())

        return {
            "avg_quoted_price_inr":         avg_price,
            "max_quoted_price_inr":         max_price,
            "min_quoted_price_inr":         min_price,
            "avg_price_spread_pct":         avg_spread,
            "avg_l1_vs_l2_gap_pct":         avg_l1_l2_gap,
            "bids_with_abnormal_spread":    abnormal_count,
        }

    def _anomaly_report(self, vendors_df: pd.DataFrame) -> Dict[str, Any]:
        if vendors_df.empty:
            return {"note": "No vendor evaluation data for anomaly analysis."}

        flags = {
            "single_vendor_bids":     "anomaly_single_vendor",
            "abnormal_price_spreads": "anomaly_abnormal_spread",
            "missing_l1_mappings":    "anomaly_missing_rank",
            "duplicate_quoted_prices":"anomaly_duplicate_price",
            "low_participation_bids": "anomaly_low_participation",
        }

        report: Dict[str, Any] = {}
        total_anomalies = 0
        for label, col in flags.items():
            if col in vendors_df.columns:
                # Count distinct bids (not rows) with this anomaly
                count = int(
                    vendors_df[vendors_df[col]]["bid_id"].nunique()
                    if "bid_id" in vendors_df.columns
                    else vendors_df[col].sum()
                )
                report[label] = count
                total_anomalies += count
            else:
                report[label] = 0

        report["total_anomaly_flags"] = total_anomalies
        report["anomaly_risk_level"] = (
            "HIGH" if total_anomalies > 5 else
            "MEDIUM" if total_anomalies > 1 else
            "LOW"
        )
        return report

    def _category_intelligence(
        self, listings_df: pd.DataFrame, vendors_df: pd.DataFrame
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        if not listings_df.empty and "item_category" in listings_df.columns:
            # Truncate long category names for readability
            cats = listings_df["item_category"].dropna().str[:60]
            result["top_categories_by_bid_count"] = _top_n(cats, 10)

        if not listings_df.empty and "quantity" in listings_df.columns:
            top_qty = (
                listings_df.groupby(
                    listings_df["item_category"].str[:60]
                )["quantity"].sum()
                .nlargest(10)
                .astype(int)
                .to_dict()
            )
            result["top_categories_by_total_quantity"] = top_qty

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════════════

    def _persist_all(
        self,
        master: Dict[str, Any],
        listings_df: pd.DataFrame,
        vendors_df: pd.DataFrame,
        anomalies: Dict[str, Any],
        category: Dict[str, Any],
    ) -> None:
        out = self.output_dir

        # Vendor intelligence
        save_json(master["vendor"],   out / "vendor_intelligence_report.json")
        self._dict_to_csv(master["vendor"], out / "vendor_intelligence_report.csv", "vendor_intelligence")

        # Ministry intelligence
        save_json(master["ministry"], out / "ministry_intelligence_report.json")
        self._dict_to_csv(master["ministry"], out / "ministry_intelligence_report.csv", "ministry_intelligence")

        # Pricing intelligence
        save_json(master["pricing"],  out / "pricing_intelligence_report.json")
        self._dict_to_csv(master["pricing"], out / "pricing_intelligence_report.csv", "pricing_intelligence")

        # Anomaly report
        save_json(anomalies,          out / "anomaly_report.json")
        anomaly_rows = [{"anomaly_type": k, "count": v} for k, v in anomalies.items()]
        save_csv(anomaly_rows,        out / "anomaly_report.csv")

        # Category intelligence
        save_json(category,           out / "category_intelligence_report.json")
        self._dict_to_csv(category, out / "category_intelligence_report.csv", "category_intelligence")

        self.logger.info("All sub-reports persisted to outputs/.")

    def _dict_to_csv(
        self, data: Dict[str, Any], path: Path, section_label: str
    ) -> None:
        """Flattens a nested dict into key/value/subsection CSV rows."""
        rows = []
        for key, val in data.items():
            if isinstance(val, dict):
                for subkey, subval in val.items():
                    rows.append({"section": section_label, "metric": key, "label": subkey, "value": subval})
            else:
                rows.append({"section": section_label, "metric": key, "label": "", "value": val})
        if rows:
            save_csv(rows, path)

    # ═══════════════════════════════════════════════════════════════════════
    # HTML DASHBOARD
    # ═══════════════════════════════════════════════════════════════════════

    def _generate_html_dashboard(self, master: Dict[str, Any]) -> None:
        s  = master["summary"]
        v  = master["vendor"]
        m  = master["ministry"]
        p  = master["pricing"]
        an = master["anomalies"]
        ca = master["category"]

        def _kv_table(d: Dict, title: str) -> str:
            if not d or "note" in d:
                return f"<p><em>{d.get('note','No data.')}</em></p>"
            rows = ""
            for k, val in d.items():
                if isinstance(val, dict):
                    inner = "".join(f"<tr><td>{ik}</td><td>{iv}</td></tr>" for ik, iv in list(val.items())[:10])
                    rows += f'<tr><td colspan="2"><strong>{k}</strong><table class="inner">{inner}</table></td></tr>'
                else:
                    rows += f"<tr><td>{k.replace('_',' ').title()}</td><td><strong>{val}</strong></td></tr>"
            return f"<h3>{title}</h3><table>{rows}</table>"

        anomaly_risk = an.get("anomaly_risk_level", "LOW")
        risk_color   = {"HIGH": "#e74c3c", "MEDIUM": "#f39c12", "LOW": "#27ae60"}.get(anomaly_risk, "#27ae60")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GeM Procurement Intelligence Dashboard</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#0f1117;color:#e0e0e0;padding:24px}}
  h1{{font-size:1.8rem;color:#7dd3fc;margin-bottom:4px}}
  .subtitle{{color:#64748b;font-size:.9rem;margin-bottom:28px}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-bottom:28px}}
  .card{{background:#1e2230;border-radius:10px;padding:20px;border:1px solid #2a2f3d}}
  .card h3{{font-size:.95rem;color:#7dd3fc;margin-bottom:14px;text-transform:uppercase;letter-spacing:.05em}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem}}
  td{{padding:6px 8px;border-bottom:1px solid #2a2f3d;vertical-align:top}}
  td:first-child{{color:#94a3b8;width:55%}}
  td:last-child strong{{color:#e2e8f0}}
  table.inner{{margin-top:8px;background:#161a24;border-radius:6px}}
  table.inner td{{color:#94a3b8;font-size:.8rem}}
  .stat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:28px}}
  .stat{{background:#1e2230;border-radius:10px;padding:18px 20px;border:1px solid #2a2f3d;text-align:center}}
  .stat .num{{font-size:2rem;font-weight:700;color:#7dd3fc}}
  .stat .lbl{{font-size:.78rem;color:#64748b;margin-top:4px}}
  .risk-badge{{display:inline-block;padding:4px 14px;border-radius:20px;font-weight:700;
               background:{risk_color}22;color:{risk_color};border:1px solid {risk_color}55}}
  footer{{text-align:center;color:#374151;font-size:.78rem;margin-top:32px}}
</style>
</head>
<body>
<h1>🏛️ GeM Procurement Intelligence Dashboard</h1>
<p class="subtitle">Generated: {ISO_NOW} &nbsp;|&nbsp; Platform: gemedge-procurement-intelligence-scraper</p>

<div class="stat-grid">
  <div class="stat"><div class="num">{s.get('total_bids_analyzed',0)}</div><div class="lbl">Bids Analyzed</div></div>
  <div class="stat"><div class="num">{s.get('total_unique_vendors',0)}</div><div class="lbl">Unique Vendors</div></div>
  <div class="stat"><div class="num">{s.get('total_awarded_contracts',0)}</div><div class="lbl">Awarded Contracts</div></div>
  <div class="stat"><div class="num">{s.get('total_vendor_evaluation_rows',0)}</div><div class="lbl">Evaluation Rows</div></div>
  <div class="stat"><div class="num">{an.get('total_anomaly_flags',0)}</div><div class="lbl">Anomaly Flags<br><span class="risk-badge">{anomaly_risk}</span></div></div>
</div>

<div class="grid">
  <div class="card">{_kv_table({"Top Winning Vendors": v.get("top_winning_vendors",{}), "Avg Awarded Value (INR)": v.get("average_awarded_value_inr","N/A")}, "Vendor Intelligence")}</div>
  <div class="card">{_kv_table({"Top Ministries": m.get("top_ministries_by_bid_count",{}), "Avg Competition / Bid": m.get("avg_competition_per_bid","N/A"), "Top Ministry Concentration": str(m.get("top_ministry_concentration_pct","N/A"))+"%"}, "Ministry Intelligence")}</div>
  <div class="card">{_kv_table({k: v for k,v in p.items() if "note" not in k}, "Pricing Intelligence")}</div>
  <div class="card">{_kv_table({k: v for k,v in an.items() if k not in ("total_anomaly_flags","anomaly_risk_level","note")}, "Anomaly Breakdown")}</div>
  <div class="card">{_kv_table({"Top Categories": ca.get("top_categories_by_bid_count",{})}, "Category Intelligence")}</div>
  <div class="card">{_kv_table({"Top Vendors by Participation": v.get("top_vendors_by_participation",{})}, "Participation Rankings")}</div>
</div>

<footer>GeM Procurement Intelligence Platform &copy; {datetime.now().year} &nbsp;|&nbsp; All data sourced from GeM Portal</footer>
</body>
</html>"""

        html_path = self.output_dir / "procurement_intelligence_dashboard.html"
        html_path.write_text(html, encoding="utf-8")
        self.logger.info(f"HTML dashboard saved: {html_path}")

    # ═══════════════════════════════════════════════════════════════════════
    # EXECUTIVE SUMMARY
    # ═══════════════════════════════════════════════════════════════════════

    def _generate_executive_summary(self, master: Dict[str, Any]) -> None:
        s  = master["summary"]
        v  = master["vendor"]
        m  = master["ministry"]
        p  = master["pricing"]
        an = master["anomalies"]

        top_winner   = next(iter(v.get("top_winning_vendors", {})), "N/A")
        top_ministry = next(iter(m.get("top_ministries_by_bid_count", {})), "N/A")
        top_ministry_count = m.get("top_ministries_by_bid_count", {}).get(top_ministry, 0)

        anomaly_lines = "\n".join(
            f"- **{k.replace('_',' ').title()}**: {val}"
            for k, val in an.items()
            if k not in ("total_anomaly_flags", "anomaly_risk_level", "note") and isinstance(val, int)
        )

        top_vendors_lines = "\n".join(
            f"  {i+1}. {vendor} — {wins} win(s)"
            for i, (vendor, wins) in enumerate(list(v.get("top_winning_vendors", {}).items())[:5])
        )

        top_part_lines = "\n".join(
            f"  {i+1}. {vendor} — {cnt} bid(s)"
            for i, (vendor, cnt) in enumerate(list(v.get("top_vendors_by_participation", {}).items())[:5])
        )

        avg_comp = m.get("avg_competition_per_bid", "N/A")
        avg_spread = p.get("avg_price_spread_pct", "N/A")
        avg_price = p.get("avg_quoted_price_inr", "N/A")

        avg_price_str = f"₹{avg_price:,.2f}" if isinstance(avg_price, float) else str(avg_price)

        md = textwrap.dedent(f"""\
        # GeM Procurement Intelligence — Executive Summary

        **Generated:** {ISO_NOW}
        **Platform:** gemedge-procurement-intelligence-scraper

        ---

        ## 📊 Dataset Overview

        | Metric | Value |
        |---|---|
        | Total Bids Analyzed | {s.get('total_bids_analyzed', 0)} |
        | Unique Vendors | {s.get('total_unique_vendors', 0)} |
        | Awarded Contracts | {s.get('total_awarded_contracts', 0)} |
        | Vendor Evaluation Rows | {s.get('total_vendor_evaluation_rows', 0)} |

        ---

        ## 🏆 Top Winning Vendors

        {top_vendors_lines if top_vendors_lines else "*(No awarded vendor data available)*"}

        ## 📈 Most Active Participants

        {top_part_lines if top_part_lines else "*(No participation data available)*"}

        ---

        ## 🏛️ Ministry Intelligence

        - **Most Active Ministry:** {top_ministry} ({top_ministry_count} bids)
        - **Top Ministry Concentration:** {m.get('top_ministry_concentration_pct', 'N/A')}% of all bids
        - **Average Vendor Competition per Bid:** {avg_comp}

        ---

        ## 💰 Pricing Intelligence

        - **Average Quoted Price (INR):** {avg_price_str}
        - **Average Price Spread:** {avg_spread}%
        - **Bids with Abnormal Price Spread:** {p.get('bids_with_abnormal_spread', 0)}

        ---

        ## ⚠️ Procurement Risk & Anomaly Findings

        **Overall Risk Level:** `{an.get('anomaly_risk_level', 'LOW')}`
        **Total Anomaly Flags:** {an.get('total_anomaly_flags', 0)}

        {anomaly_lines}

        ---

        ## 🔍 Key Observations

        1. The procurement dataset is dominated by **{top_ministry}**, representing the highest
           bid activity among all ministries.
        2. Average competition per bid stands at **{avg_comp} vendors**, indicating
           {"healthy competition" if isinstance(avg_comp, (int,float)) and avg_comp >= 3 else "low competition levels requiring scrutiny"}.
        3. Pricing spread analytics reveal an average spread of **{avg_spread}%** between
           competing bids, {"suggesting competitive market dynamics" if isinstance(avg_spread,(int,float)) and avg_spread < 50 else "suggesting potentially abnormal pricing patterns"}.
        4. Top winning vendor **{top_winner}** shows repeated procurement success
           — further due-diligence on monopoly risk is recommended.

        ---

        *This report was auto-generated by the gemedge-procurement-intelligence-scraper platform.*
        """)

        summary_path = self.output_dir / "executive_summary.md"
        summary_path.write_text(md, encoding="utf-8")
        self.logger.info(f"Executive summary saved: {summary_path}")
