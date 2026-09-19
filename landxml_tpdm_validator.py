"""
TPDM LandXML Alignment Compliance Validator
===========================================
This module parses LandXML (v1.0 - v1.2) highway alignment files and validates
horizontal geometric elements (curves, spiral transitions) and vertical profile
elements (grades, PVI vertical curves) against Hong Kong Transport Department
Transport Planning and Design Manual (TPDM Vol. 2 Chapter 3) geometric requirements.
"""

import xml.etree.ElementTree as ET
import csv
import math
from typing import Dict, List, Any, Optional, Tuple


# =======================================================================
# TPDM (August 2026 Edition - Vol. 2 Ch. 3) Geometric Parameter Table
# =======================================================================
TPDM_STANDARDS = {
    "Trunk Road / Expressway": {
        "design_speed_kph": 100,
        "min_radius_desirable_m": 570.0,
        "min_radius_absolute_m": 410.0,
        "min_transition_length_m": 70.0,
        "max_gradient_desirable_pct": 4.0,
        "max_gradient_absolute_pct": 6.0,
        "min_gradient_drainage_pct": 0.5,
        "min_crest_k_value": 74.0,
        "min_sag_k_value": 37.0,
    },
    "Primary Distributor (High Speed)": {
        "design_speed_kph": 80,
        "min_radius_desirable_m": 340.0,
        "min_radius_absolute_m": 250.0,
        "min_transition_length_m": 50.0,
        "max_gradient_desirable_pct": 6.0,
        "max_gradient_absolute_pct": 8.0,
        "min_gradient_drainage_pct": 0.5,
        "min_crest_k_value": 33.0,
        "min_sag_k_value": 26.0,
    },
    "Primary Distributor (Standard)": {
        "design_speed_kph": 70,
        "min_radius_desirable_m": 250.0,
        "min_radius_absolute_m": 180.0,
        "min_transition_length_m": 45.0,
        "max_gradient_desirable_pct": 6.0,
        "max_gradient_absolute_pct": 8.0,
        "min_gradient_drainage_pct": 0.5,
        "min_crest_k_value": 20.0,
        "min_sag_k_value": 20.0,
    },
    "District Distributor": {
        "design_speed_kph": 50,
        "min_radius_desirable_m": 125.0,
        "min_radius_absolute_m": 90.0,
        "min_transition_length_m": 30.0,
        "max_gradient_desirable_pct": 8.0,
        "max_gradient_absolute_pct": 10.0,
        "min_gradient_drainage_pct": 0.5,
        "min_crest_k_value": 9.0,
        "min_sag_k_value": 13.0,
    },
    "Local Distributor": {
        "design_speed_kph": 50,
        "min_radius_desirable_m": 100.0,
        "min_radius_absolute_m": 60.0,
        "min_transition_length_m": 25.0,
        "max_gradient_desirable_pct": 8.0,
        "max_gradient_absolute_pct": 10.0,
        "min_gradient_drainage_pct": 0.5,
        "min_crest_k_value": 6.5,
        "min_sag_k_value": 11.0,
    },
}


class LandXMLGeometryParser:
    """Parses CoordGeom horizontal elements and Profile/ProfAlign vertical elements."""

    def __init__(self, filepath: str):
        self.tree = ET.parse(filepath)
        self.root = self.tree.getroot()
        # Strip XML namespaces for simplified element path queries
        self._strip_namespaces(self.root)

    @staticmethod
    def _strip_namespaces(el: ET.Element):
        if '}' in el.tag:
            el.tag = el.tag.split('}', 1)[1]
        for k in list(el.attrib.keys()):
            if '}' in k:
                new_key = k.split('}', 1)[1]
                el.attrib[new_key] = el.attrib.pop(k)
        for child in el:
            LandXMLGeometryParser._strip_namespaces(child)

    def extract_alignments(self) -> List[Dict[str, Any]]:
        alignments_data = []
        for align in self.root.iter("Alignment"):
            align_name = align.attrib.get("name", "Unnamed_Alignment")
            align_length = float(align.attrib.get("length", 0.0))
            start_sta = float(align.attrib.get("staStart", 0.0))

            horiz_elements = self._parse_coord_geom(align, start_sta)
            profiles = self._parse_profiles(align)

            alignments_data.append({
                "name": align_name,
                "length": align_length,
                "start_station": start_sta,
                "horizontal_elements": horiz_elements,
                "profiles": profiles
            })
        return alignments_data

    def _parse_coord_geom(self, align_elem: ET.Element, start_sta: float) -> List[Dict[str, Any]]:
        elements = []
        coord_geom = align_elem.find("CoordGeom")
        if coord_geom is None:
            return elements

        current_sta = start_sta
        for child in coord_geom:
            tag = child.tag
            length = float(child.attrib.get("length", 0.0))
            elem_sta_start = current_sta
            elem_sta_end = current_sta + length
            current_sta = elem_sta_end

            if tag == "Line":
                elements.append({
                    "element_type": "Line",
                    "station_start": elem_sta_start,
                    "station_end": elem_sta_end,
                    "length": length,
                })
            elif tag == "Curve":
                radius = abs(float(child.attrib.get("radius", 0.0)))
                rot = child.attrib.get("rot", "cw")
                elements.append({
                    "element_type": "Curve",
                    "station_start": elem_sta_start,
                    "station_end": elem_sta_end,
                    "length": length,
                    "radius": radius,
                    "rotation": rot,
                })
            elif tag == "Spiral":
                radius_start = abs(float(child.attrib.get("radiusStart", 0.0)))
                radius_end = abs(float(child.attrib.get("radiusEnd", 0.0)))
                spiral_type = child.attrib.get("spiType", "clothoid")
                elements.append({
                    "element_type": "Spiral",
                    "station_start": elem_sta_start,
                    "station_end": elem_sta_end,
                    "length": length,
                    "radius_start": radius_start,
                    "radius_end": radius_end,
                    "spiral_type": spiral_type,
                })
        return elements

    def _parse_profiles(self, align_elem: ET.Element) -> List[Dict[str, Any]]:
        profiles = []
        for prof in align_elem.iter("Profile"):
            prof_name = prof.attrib.get("name", "Unnamed_Profile")
            for prof_align in prof.iter("ProfAlign"):
                prof_align_name = prof_align.attrib.get("name", prof_name)
                pvis = []
                # PVI tags contain space-delimited "station elevation"
                for pvi in prof_align.iter("PVI"):
                    coords = pvi.text.strip().split()
                    if len(coords) >= 2:
                        pvis.append({
                            "type": "PVI",
                            "station": float(coords[0]),
                            "elevation": float(coords[1])
                        })

                # ParaCurve tags (symmetric vertical curves)
                para_curves = []
                for pc in prof_align.iter("ParaCurve"):
                    coords = pc.text.strip().split()
                    if len(coords) >= 2:
                        length = float(pc.attrib.get("length", 0.0))
                        para_curves.append({
                            "type": "ParaCurve",
                            "station": float(coords[0]),
                            "elevation": float(coords[1]),
                            "length": length
                        })

                # Compute tangent gradients between consecutive PVIs / ParaCurves
                combined_pts = sorted(pvis + para_curves, key=lambda x: x["station"])
                gradients = []
                for i in range(len(combined_pts) - 1):
                    p1 = combined_pts[i]
                    p2 = combined_pts[i + 1]
                    d_sta = p2["station"] - p1["station"]
                    if d_sta > 0.0001:
                        grade_pct = ((p2["elevation"] - p1["elevation"]) / d_sta) * 100.0
                        gradients.append({
                            "station_start": p1["station"],
                            "station_end": p2["station"],
                            "gradient_pct": grade_pct,
                            "length": d_sta
                        })

                profiles.append({
                    "profile_name": prof_align_name,
                    "pvis": pvis,
                    "para_curves": para_curves,
                    "gradients": gradients
                })
        return profiles


class TPDMComplianceValidator:
    """Evaluates alignment geometries against assigned TPDM standards."""

    def __init__(self, road_class: str):
        if road_class not in TPDM_STANDARDS:
            raise ValueError(f"Unknown road class '{road_class}'. Available: {list(TPDM_STANDARDS.keys())}")
        self.road_class = road_class
        self.standards = TPDM_STANDARDS[road_class]

    def validate_alignment(self, alignment: Dict[str, Any]) -> List[Dict[str, Any]]:
        violations = []
        align_name = alignment["name"]

        # 1. Validate Horizontal Curve Radii
        for elem in alignment["horizontal_elements"]:
            if elem["element_type"] == "Curve":
                r = elem["radius"]
                sta_s = elem["station_start"]
                sta_e = elem["station_end"]

                if r < self.standards["min_radius_absolute_m"]:
                    violations.append({
                        "alignment": align_name,
                        "domain": "Horizontal",
                        "element_type": "Circular Curve",
                        "station_start": f"{sta_s:.2f}",
                        "station_end": f"{sta_e:.2f}",
                        "parameter": "Radius (m)",
                        "measured_value": f"{r:.2f}",
                        "design_limit": f">= {self.standards['min_radius_absolute_m']:.2f}",
                        "severity": "CRITICAL NON-COMPLIANCE",
                        "tpdm_ref": "TPDM Vol 2 Ch 3 Table 3.3.2 (Absolute Min Radius)"
                    })
                elif r < self.standards["min_radius_desirable_m"]:
                    violations.append({
                        "alignment": align_name,
                        "domain": "Horizontal",
                        "element_type": "Circular Curve",
                        "station_start": f"{sta_s:.2f}",
                        "station_end": f"{sta_e:.2f}",
                        "parameter": "Radius (m)",
                        "measured_value": f"{r:.2f}",
                        "design_limit": f">= {self.standards['min_radius_desirable_m']:.2f}",
                        "severity": "WARNING (Below Desirable)",
                        "tpdm_ref": "TPDM Vol 2 Ch 3 Table 3.3.2 (Desirable Min Radius)"
                    })

            elif elem["element_type"] == "Spiral":
                L = elem["length"]
                sta_s = elem["station_start"]
                sta_e = elem["station_end"]
                min_L = self.standards["min_transition_length_m"]

                if L < min_L:
                    violations.append({
                        "alignment": align_name,
                        "domain": "Horizontal",
                        "element_type": "Spiral Transition",
                        "station_start": f"{sta_s:.2f}",
                        "station_end": f"{sta_e:.2f}",
                        "parameter": "Transition Length (m)",
                        "measured_value": f"{L:.2f}",
                        "design_limit": f">= {min_L:.2f}",
                        "severity": "CRITICAL NON-COMPLIANCE",
                        "tpdm_ref": "TPDM Vol 2 Ch 3 Cl 3.3.3 (Min Transition Length)"
                    })

        # 2. Validate Vertical Gradients and Vertical Curve K-values
        for prof in alignment["profiles"]:
            # Check tangent gradients
            for g in prof["gradients"]:
                abs_g = abs(g["gradient_pct"])
                sta_s = g["station_start"]
                sta_e = g["station_end"]

                # Maximum gradient check
                if abs_g > self.standards["max_gradient_absolute_pct"]:
                    violations.append({
                        "alignment": f"{align_name} ({prof['profile_name']})",
                        "domain": "Vertical",
                        "element_type": "Tangent Grade",
                        "station_start": f"{sta_s:.2f}",
                        "station_end": f"{sta_e:.2f}",
                        "parameter": "Longitudinal Gradient (%)",
                        "measured_value": f"{g['gradient_pct']:.2f}%",
                        "design_limit": f"<= {self.standards['max_gradient_absolute_pct']:.2f}%",
                        "severity": "CRITICAL NON-COMPLIANCE",
                        "tpdm_ref": "TPDM Vol 2 Ch 3 Table 3.4.2 (Absolute Max Grade)"
                    })
                elif abs_g > self.standards["max_gradient_desirable_pct"]:
                    violations.append({
                        "alignment": f"{align_name} ({prof['profile_name']})",
                        "domain": "Vertical",
                        "element_type": "Tangent Grade",
                        "station_start": f"{sta_s:.2f}",
                        "station_end": f"{sta_e:.2f}",
                        "parameter": "Longitudinal Gradient (%)",
                        "measured_value": f"{g['gradient_pct']:.2f}%",
                        "design_limit": f"<= {self.standards['max_gradient_desirable_pct']:.2f}%",
                        "severity": "WARNING (Below Desirable)",
                        "tpdm_ref": "TPDM Vol 2 Ch 3 Table 3.4.2 (Desirable Max Grade)"
                    })

                # Minimum gradient drainage check
                if abs_g < self.standards["min_gradient_drainage_pct"]:
                    violations.append({
                        "alignment": f"{align_name} ({prof['profile_name']})",
                        "domain": "Vertical",
                        "element_type": "Tangent Grade",
                        "station_start": f"{sta_s:.2f}",
                        "station_end": f"{sta_e:.2f}",
                        "parameter": "Drainage Gradient (%)",
                        "measured_value": f"{g['gradient_pct']:.2f}%",
                        "design_limit": f">= {self.standards['min_gradient_drainage_pct']:.2f}%",
                        "severity": "DRAINAGE RISK",
                        "tpdm_ref": "TPDM Vol 2 Ch 3 Cl 3.4.4 (Pavement Drainage Min Grade)"
                    })

            # Check ParaCurve K-values
            para_curves = prof["para_curves"]
            grads = prof["gradients"]
            for pc in para_curves:
                pc_sta = pc["station"]
                pc_L = pc["length"]
                # Find preceding and succeeding grades
                g_in = None
                g_out = None
                for g in grads:
                    if abs(g["station_end"] - pc_sta) < 0.1:
                        g_in = g["gradient_pct"]
                    if abs(g["station_start"] - pc_sta) < 0.1:
                        g_out = g["gradient_pct"]

                if g_in is not None and g_out is not None:
                    A = abs(g_out - g_in)  # Algebraic difference in grade
                    if A > 0.001 and pc_L > 0:
                        k_val = pc_L / A
                        is_crest = (g_in > g_out)
                        req_k = self.standards["min_crest_k_value"] if is_crest else self.standards["min_sag_k_value"]
                        curve_kind = "Crest Curve" if is_crest else "Sag Curve"

                        if k_val < req_k:
                            violations.append({
                                "alignment": f"{align_name} ({prof['profile_name']})",
                                "domain": "Vertical",
                                "element_type": f"ParaCurve ({curve_kind})",
                                "station_start": f"{pc_sta - (pc_L/2):.2f}",
                                "station_end": f"{pc_sta + (pc_L/2):.2f}",
                                "parameter": "K-Value (m/%)",
                                "measured_value": f"{k_val:.2f}",
                                "design_limit": f">= {req_k:.2f}",
                                "severity": "CRITICAL NON-COMPLIANCE",
                                "tpdm_ref": f"TPDM Vol 2 Ch 3 Table 3.4.5 (Min {curve_kind} K-value)"
                            })

        return violations


def export_violations_to_csv(violations: List[Dict[str, Any]], output_filepath: str):
    """Exports structured validation violations into an audit CSV report."""
    fieldnames = [
        "alignment",
        "domain",
        "element_type",
        "station_start",
        "station_end",
        "parameter",
        "measured_value",
        "design_limit",
        "severity",
        "tpdm_ref"
    ]
    with open(output_filepath, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in violations:
            writer.writerow(row)


# =======================================================================
# Verification & Self-Test Suite
# =======================================================================
if __name__ == "__main__":
    # Generates a synthetic LandXML file with deliberate compliance infractions
    sample_landxml = """<?xml version="1.0" encoding="UTF-8"?>
<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" version="1.2" date="2026-09-19">
    <Alignments>
        <Alignment name="Route_A_PrimaryDistributor" length="1200.00" staStart="0.00">
            <CoordGeom>
                <Line length="200.00">
                    <Start>830000.00 815000.00</Start>
                    <End>830200.00 815000.00</End>
                </Line>
                <!-- Non-compliant transition length (35m vs required 50m) -->
                <Spiral length="35.00" radiusStart="0.0" radiusEnd="200.0" rot="cw" spiType="clothoid">
                    <Start>830200.00 815000.00</Start>
                    <End>830235.00 814995.00</End>
                </Spiral>
                <!-- Non-compliant curve radius (200m vs desirable 340m / absolute 250m) -->
                <Curve length="250.00" radius="200.00" rot="cw">
                    <Start>830235.00 814995.00</Start>
                    <End>830450.00 814850.00</End>
                </Curve>
                <Line length="715.00">
                    <Start>830450.00 814850.00</Start>
                    <End>831100.00 814500.00</End>
                </Line>
            </CoordGeom>
            <Profile name="Route_A_Profile">
                <ProfAlign name="Route_A_Finished_Level">
                    <PVI>0.00 50.00</PVI>
                    <!-- Critical steep gradient 9.0% vs max 8.0% -->
                    <ParaCurve length="60.00">300.00 77.00</ParaCurve>
                    <!-- Near flat gradient 0.2% vs min drainage 0.5% -->
                    <PVI>700.00 77.80</PVI>
                    <PVI>1200.00 95.00</PVI>
                </ProfAlign>
            </Profile>
        </Alignment>
    </Alignments>
</LandXML>"""

    test_xml_path = "sample_alignment.xml"
    output_report_path = "tpdm_compliance_audit_report.csv"

    with open(test_xml_path, "w", encoding="utf-8") as f:
        f.write(sample_landxml)

    # 1. Parse LandXML
    parser = LandXMLGeometryParser(test_xml_path)
    alignments = parser.extract_alignments()

    # 2. Validate against TPDM August 2026 Primary Distributor (High Speed 80 km/h)
    validator = TPDMComplianceValidator(road_class="Primary Distributor (High Speed)")
    all_violations = []
    for align in alignments:
        issues = validator.validate_alignment(align)
        all_violations.extend(issues)

    # 3. Export to CSV Report
    export_violations_to_csv(all_violations, output_report_path)
    print(f"Audit completed: {len(all_violations)} violations flagged and written to {output_report_path}")
