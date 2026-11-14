"""NEXUS domain taxonomy.

This file is *team-authored domain knowledge*, not retrieved data. It contains:

* CAPABILITIES   - normalised capability vocabulary with Swedish/English keyword stems
* ROLE_RELATIONS - generic, directed "A enables/feeds B" relations between value-chain roles
* CAPABILITY_RELATIONS - explicit, stronger relations between specific capabilities
* DOMAINS        - application domains shared by capabilities
* CONCEPTS       - application concept library used for multi-company discovery

Nothing in here is a fact about any company. Companies are only linked to capabilities
through evidence sentences retrieved from public sources (see agents/company_agent.py).
Concepts are hypotheses templates; every output built from them is labelled HYPOTHESIS.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TAXONOMY_VERSION = "2026.11-1"

# Value-chain roles ---------------------------------------------------------------
ROLES = {
    "SENSING": "Produces measurements or situational data",
    "PLATFORM": "Physical carrier: vessel, vehicle or system that operates at sea",
    "CONNECTIVITY": "Moves data between assets, vessels and shore",
    "DATA_AI": "Turns data into insight, predictions or visual understanding",
    "SOFTWARE": "Builds and integrates digital and embedded systems",
    "ENERGY": "Energy generation, transmission or grid assets",
    "MARINE_OPS": "Installs, builds, maintains or repairs things at sea / under water",
    "ENGINEERING": "Designs physical structures and components",
    "ASSURANCE": "Tests, certifies or secures systems",
    "ENABLER": "Financing, advisory, education and other support functions",
    "NEED_OWNER": "Public body or operator with an operational need (potential problem owner)",
}

DOMAINS = {
    "underwater_monitoring": "Underwater and seabed monitoring",
    "maritime_surveillance": "Maritime surveillance and situational awareness",
    "offshore_energy": "Offshore energy and subsea power/telecom infrastructure",
    "vessel_operations": "Vessel and fleet operations",
    "autonomous_maritime": "Autonomous and unmanned maritime systems",
    "smart_grid": "Smart energy grids and utilities",
    "defence_security": "Defence, security and resilience",
    "coastal_infrastructure": "Ports, quays and coastal construction",
    "marine_environment": "Marine environment and sustainability",
    "digital_services": "Digital products and services",
}


@dataclass(frozen=True)
class Capability:
    id: str
    name: str
    role: str
    description: str
    keywords: tuple[str, ...]  # regex fragments, matched case-insensitively at word start
    domains: tuple[str, ...]
    openalex_query: str = ""


def _c(id, name, role, description, keywords, domains, q=""):
    return Capability(id, name, role, description, tuple(keywords), tuple(domains), q)


_CAPS = [
    _c("hydroacoustics", "Hydroacoustics & sonar", "SENSING",
       "Underwater acoustic sensing such as sonar, echo sounders and hydroacoustic systems.",
       [r"hydroakusti", r"hydroacousti", r"sonar", r"ekolod", r"echo ?sounder", r"underwater acoustic"],
       ["underwater_monitoring", "maritime_surveillance", "offshore_energy", "autonomous_maritime"],
       "underwater acoustic sonar seabed monitoring"),
    _c("underwater_sensors", "Underwater sensor systems", "SENSING",
       "Sensors and measurement stations deployed under water or at sea.",
       [r"uv-sensor", r"undervattenssensor", r"sensorsystem", r"marina mätstation", r"underwater sensor",
        r"mätstation", r"sensor system"],
       ["underwater_monitoring", "maritime_surveillance", "marine_environment", "offshore_energy"],
       "underwater sensor network marine monitoring"),
    _c("maritime_surveillance", "Maritime surveillance systems", "SENSING",
       "Systems for surveillance and reconnaissance of sea areas.",
       [r"sjöövervakning", r"sjöbevakning", r"maritime surveillance", r"havsövervakning", r"spaning"],
       ["maritime_surveillance", "defence_security", "autonomous_maritime"],
       "maritime surveillance vessel detection tracking"),
    _c("marine_navigation", "Marine navigation systems", "SENSING",
       "Navigation, positioning and bridge systems for vessels.",
       [r"navigation", r"radar(?![- ]?(?:group|gruppen))", r"gyro", r"ecdis", r"\bais\b"],  # "Radar Group" is a survey firm
       ["vessel_operations", "autonomous_maritime", "maritime_surveillance"],
       "autonomous vessel navigation maritime positioning"),
    _c("seabed_survey", "Seabed survey & inspection", "SENSING",
       "Survey of the seabed, cable routes and underwater structures.",
       [r"\bsurvey", r"sjömätning", r"bottenkartering", r"bottenundersökning", r"undervattensinspektion",
        r"underwater inspection"],
       ["underwater_monitoring", "offshore_energy", "coastal_infrastructure"],
       "seabed survey subsea cable route inspection"),
    _c("environmental_monitoring", "Environmental monitoring", "SENSING",
       "Monitoring of environmental conditions, emissions or biodiversity.",
       [r"miljöövervakning", r"environmental monitoring", r"biodiversity", r"biologisk mångfald",
        r"miljöräddning", r"miljömätning"],
       ["marine_environment", "underwater_monitoring"],
       "marine environmental monitoring Baltic Sea sensors"),
    _c("marine_communication", "Maritime communication systems", "CONNECTIVITY",
       "Radio, satellite and on-board communication systems for the maritime sector.",
       [r"satcom", r"vsat", r"radiokommunikation", r"marin kommunikation", r"maritime communication",
        r"kommunikationsutrustning", r"kommunikation \(radio", r"radio(?:länk|system|utrustning)",
        r"kommunikation, it"],
       ["vessel_operations", "maritime_surveillance", "autonomous_maritime", "defence_security"],
       "maritime wireless communication vessel to shore"),
    _c("iot_telematics", "IoT & telematics", "CONNECTIVITY",
       "Connected devices, telematics and remote monitoring of assets and fleets.",
       [r"\biot\b", r"telemati", r"fleet ?monitor", r"sim-kort", r"\bm2m\b", r"uppkopplade?",
        r"internet of things", r"fjärrövervakning"],
       ["vessel_operations", "smart_grid", "underwater_monitoring", "marine_environment", "offshore_energy"],
       "internet of things remote monitoring maritime assets"),
    _c("telecom_networks", "Telecom networks", "CONNECTIVITY",
       "Mobile and fixed telecommunication networks and infrastructure.",
       [r"\b5g\b", r"telekommunikationsnät", r"mobilnät", r"telecom\b", r"mobil datakommunikation",
        r"datakommunikation", r"meddelandetjänst", r"informations- och kommunikationsteknik"],
       ["digital_services", "smart_grid", "vessel_operations", "defence_security"],
       "5G maritime coverage private networks industry"),
    _c("embedded_systems", "Embedded systems & electronics", "SOFTWARE",
       "Development of electronics, embedded software and hardware products.",
       [r"inbyggda system", r"embedded", r"elektronik", r"hårdvaru"],
       ["underwater_monitoring", "autonomous_maritime", "defence_security", "smart_grid"],
       "embedded systems low power marine electronics"),
    _c("software_development", "Software & systems development", "SOFTWARE",
       "Custom software, system integration and application development.",
       [r"mjukvaruutveckling", r"systemutveckling", r"programvaruutveckling", r"programutveckling",
        r"software development", r"apputveckling", r"systemintegration", r"dataprogrammering",
        r"mjukvarulösning", r"programmering"],
       ["digital_services", "vessel_operations", "smart_grid"],
       ""),
    _c("ai_ml", "AI & machine learning", "DATA_AI",
       "Artificial intelligence, machine learning and advanced data analytics.",
       [r"\bai\b", r"maskininlärning", r"machine learning", r"artificiell intelligens",
        r"artificial intelligence", r"dataanalys"],
       ["maritime_surveillance", "underwater_monitoring", "smart_grid", "vessel_operations",
        "autonomous_maritime", "offshore_energy", "digital_services"],
       "machine learning anomaly detection underwater sensor data"),
    _c("visualisation_xr", "3D visualisation & interactive media", "DATA_AI",
       "Photorealistic visualisation, animation and interactive digital experiences.",
       [r"visualisering", r"visualization", r"animation", r"interaktiva upplevelser", r"\bxr\b", r"\bvr\b"],
       ["offshore_energy", "coastal_infrastructure", "digital_services", "underwater_monitoring"],
       "digital twin 3D visualization subsea infrastructure"),
    _c("cloud_infrastructure", "Cloud & IT infrastructure", "SOFTWARE",
       "Cloud platforms, hosting and IT infrastructure operations.",
       [r"moln", r"\bcloud\b", r"hosting", r"webbhotell", r"it-infrastruktur", r"infrastruktur som tjänst"],
       ["digital_services", "smart_grid", "vessel_operations", "defence_security"],
       ""),
    _c("cybersecurity", "Cybersecurity (IT/OT)", "ASSURANCE",
       "Security of IT and operational technology, risk management and compliance.",
       [r"cybersäkerhet", r"it-säkerhet", r"ot-säkerhet", r"informationssäkerhet", r"cyber ?security",
        r"it- och ot-säkerhet"],
       ["vessel_operations", "smart_grid", "defence_security", "autonomous_maritime", "digital_services",
        "offshore_energy"],
       "maritime cybersecurity operational technology vessels"),
    _c("subsea_cable_ops", "Subsea cable installation & repair", "MARINE_OPS",
       "Installation, maintenance and repair of submarine power and telecom cables.",
       [r"sjökabel", r"undervattenskabl", r"submarine (?:fib(?:er|re)[- ]optic )?cable", r"cable installation",
        r"cable repair", r"cable recover", r"kabelinstallation"],
       ["offshore_energy", "underwater_monitoring"],
       "submarine power cable fault detection monitoring"),
    _c("power_cables", "High-voltage power cables", "ENERGY",
       "Design and production of high-voltage cables and power transmission links.",
       [r"högspänningskabl", r"kraftkabel", r"elkraft", r"high-voltage cables?", r"power cables? (?:design|manufactur|production)"],
       ["offshore_energy", "smart_grid"],
       "high voltage submarine cable condition monitoring"),
    _c("wave_energy", "Wave energy conversion", "ENERGY",
       "Power plants producing electricity from ocean waves.",
       [r"vågkraft", r"havsvågor", r"wave energy", r"wave power"],
       ["offshore_energy", "marine_environment"],
       "wave energy converter mooring power take-off"),
    _c("offshore_wind", "Offshore wind", "ENERGY",
       "Offshore wind farms and their electrical infrastructure.",
       [r"vindkraft", r"wind ?farms?", r"offshore wind", r"havsbaserad vind", r"windfarm"],
       ["offshore_energy", "marine_environment"],
       "offshore wind farm inter-array cable installation"),
    _c("energy_grid", "Energy grids & utilities", "ENERGY",
       "Electricity distribution, district heating and grid monitoring.",
       [r"elnät", r"smart ?grids?", r"energisystem", r"levererar el\b", r"feldetekter"],
       ["smart_grid"],
       "smart grid fault detection distribution network monitoring"),
    _c("naval_architecture", "Naval architecture & vessel design", "ENGINEERING",
       "Concept and basic design of ships and marine structures.",
       [r"fartygsdesign", r"fartygskonstruktion", r"naval architecture", r"marine engineering",
        r"vessel design", r"skeppsbygg", r"lightweight vessels"],
       ["vessel_operations", "autonomous_maritime", "defence_security", "offshore_energy"],
       "unmanned surface vessel hull design"),
    _c("composite_structures", "Composite & lightweight structures", "ENGINEERING",
       "Structural design of composite and lightweight constructions.",
       [r"komposit", r"composite", r"lightweight", r"lättvikt"],
       ["autonomous_maritime", "offshore_energy", "vessel_operations"],
       "composite structures marine lightweight design fatigue"),
    _c("sealing_systems", "Cable & pipe sealing systems", "ENGINEERING",
       "Modular seals protecting cable and pipe penetrations.",
       [r"tätningslösning", r"tätning", r"sealing", r"kabelgenomföring"],
       ["offshore_energy", "vessel_operations", "smart_grid"],
       ""),
    _c("commercial_diving", "Commercial diving & underwater works", "MARINE_OPS",
       "Diving-based construction, inspection and repair under water.",
       [r"dykeri", r"anläggningsdyk", r"dykare", r"dykuppdrag", r"dykarbete", r"undervattensrelaterade",
        r"commercial diving", r"tjänster inom .{0,40}\bdyk\b"],
       ["coastal_infrastructure", "underwater_monitoring", "offshore_energy"],
       "underwater inspection remotely operated vehicle diver"),
    _c("dredging_marine_civil", "Dredging & marine civil works", "MARINE_OPS",
       "Dredging, quay construction and other marine contracting.",
       [r"muddring", r"kajbygg", r"vattenentreprenad", r"marina entreprenad", r"dredging"],
       ["coastal_infrastructure", "marine_environment"],
       "environmental dredging sediment turbidity monitoring"),
    _c("underwater_vehicles", "Underwater & unmanned vehicles", "PLATFORM",
       "ROVs, AUVs, submarines and other unmanned or underwater vehicles.",
       [r"\brov\b", r"\bauv\b", r"undervattensfarkost", r"ubåt", r"submarines?\b(?! (?:fib|cable|power))",
        r"obemannade?", r"unmanned", r"autonoma? (?:farkost|system)"],
       ["underwater_monitoring", "autonomous_maritime", "offshore_energy", "defence_security",
        "maritime_surveillance"],
       "autonomous underwater vehicle inspection"),
    _c("underwater_technology", "Underwater technology development", "ENGINEERING",
       "Engineering expertise in underwater and marine technology products.",
       [r"undervattensteknik", r"marinteknik", r"underwater technology", r"marine technology"],
       ["underwater_monitoring", "autonomous_maritime", "defence_security"],
       "underwater technology product development"),
    _c("naval_defence_systems", "Naval & defence systems", "PLATFORM",
       "Naval vessels and defence-related products and systems.",
       [r"örlogs", r"försvarsområdet", r"militärt försvar", r"naval (?:defen|system)", r"försvarsmateriel"],
       ["defence_security", "maritime_surveillance"],
       ""),
    _c("vessel_operator", "Vessel & ferry operations", "PLATFORM",
       "Operation of ferries, work boats or other vessels.",
       [r"färje", r"passagerar- och frakt", r"skärgårdstrafik"],
       ["vessel_operations", "marine_environment"],
       "ferry operations energy efficiency monitoring"),
    _c("testing_certification", "Testing, inspection & certification", "ASSURANCE",
       "Independent testing, inspection and certification services.",
       [r"provning", r"besiktning", r"certifieringsorgan", r"testing, inspection", r"ce-märkning"],
       ["offshore_energy", "vessel_operations", "defence_security", "digital_services"],
       ""),
    _c("system_safety", "System safety & technical documentation", "ASSURANCE",
       "System safety, integrated logistics support and technical documentation.",
       [r"systemsäkerhet", r"\bils\b", r"teknisk dokumentation", r"tekniskt systemstöd"],
       ["defence_security", "autonomous_maritime"],
       ""),
    _c("water_treatment", "Water & wastewater treatment", "ENGINEERING",
       "Products for wastewater treatment and water management.",
       [r"avloppsrening", r"reningsverk", r"vattenhantering", r"wastewater"],
       ["marine_environment"],
       "decentralised wastewater treatment nutrient Baltic Sea"),
    _c("sustainability_advisory", "Sustainability advisory", "ENABLER",
       "Sustainability policy, materiality analysis and reporting.",
       [r"hållbarhetspolicy", r"hållbarhetsrapport", r"väsentlighetsanalys"],
       ["marine_environment"], ""),
    _c("funding_advisory", "Financing & business advisory", "ENABLER",
       "Loans, venture capital, incubation and business development advice.",
       [r"riskkapital", r"\blån\b", r"inkubator", r"investeringar i (?:bolag|företag|startups?)",r"företagsutveckling"],
       ["digital_services"], ""),
    _c("research_education", "Research & higher education", "ENABLER",
       "Academic research and education.",
       [r"utbildning och forskning", r"högskola", r"universitet"],
       ["digital_services", "underwater_monitoring"], ""),
    _c("project_management", "Project & change management", "ENABLER",
       "Project management, process optimisation and change leadership.",
       [r"projektledning", r"processoptimering", r"förändringsledning", r"project management"],
       ["digital_services"], ""),
    _c("public_maritime_authority", "Public maritime mandate", "NEED_OWNER",
       "Public responsibility for maritime surveillance, rescue or defence procurement.",
       [r"ansvarar för sjöövervakning", r"miljöräddningstjänst", r"marina förband", r"upphandla, utveckla"],
       ["maritime_surveillance", "defence_security", "marine_environment"], ""),
]

CAPABILITIES: dict[str, Capability] = {c.id: c for c in _CAPS}

_PATTERNS = {
    c.id: re.compile(r"(?<![\wåäöÅÄÖ])(?:" + "|".join(c.keywords) + r")", re.IGNORECASE) for c in _CAPS
}

# Directed role relations: (source role, target role) -> (weight 0..1, rationale)
ROLE_RELATIONS: dict[tuple[str, str], tuple[float, str]] = {
    ("SENSING", "DATA_AI"): (0.80, "sensor data becomes the input for analytics and AI models"),
    ("SENSING", "CONNECTIVITY"): (0.65, "measurements need a link to shore or to other assets"),
    ("PLATFORM", "SENSING"): (0.75, "a vessel or vehicle carries the sensor payload"),
    ("MARINE_OPS", "SENSING"): (0.65, "offshore work needs survey, inspection and monitoring data"),
    ("MARINE_OPS", "PLATFORM"): (0.55, "marine operations deploy and use vehicles and vessels"),
    ("ENGINEERING", "PLATFORM"): (0.60, "structural design feeds the platform that is built and operated"),
    ("ENGINEERING", "ENERGY"): (0.50, "engineering design is needed for offshore energy devices"),
    ("ENERGY", "MARINE_OPS"): (0.80, "offshore energy assets must be installed and maintained at sea"),
    ("ENERGY", "SENSING"): (0.60, "energy assets need condition monitoring"),
    ("CONNECTIVITY", "DATA_AI"): (0.50, "connected data streams feed analytics"),
    ("SOFTWARE", "SENSING"): (0.50, "embedded and system software integrates sensors into products"),
    ("SOFTWARE", "DATA_AI"): (0.40, "software platforms operationalise models"),
    ("DATA_AI", "MARINE_OPS"): (0.50, "analytics supports planning and decisions in marine operations"),
    ("ASSURANCE", "PLATFORM"): (0.45, "platforms need verification, certification or cyber protection"),
    ("ASSURANCE", "CONNECTIVITY"): (0.45, "connected systems need security and compliance"),
    ("ASSURANCE", "ENERGY"): (0.40, "energy infrastructure needs testing and protection"),
    ("NEED_OWNER", "SENSING"): (0.45, "a public mandate defines the need that sensing solutions address"),
    ("NEED_OWNER", "PLATFORM"): (0.40, "a public mandate defines the need for platforms"),
}

# Explicit capability-level relations (undirected lookup, strongest signal).
CAPABILITY_RELATIONS: dict[frozenset, tuple[float, str]] = {
    frozenset(k): v
    for k, v in {
        ("hydroacoustics", "subsea_cable_ops"): (1.0, "acoustic survey locates cables and faults before and after installation or repair"),
        ("hydroacoustics", "underwater_vehicles"): (0.95, "sonar is the primary perception payload for underwater vehicles"),
        ("hydroacoustics", "ai_ml"): (0.9, "acoustic data can be classified automatically with machine learning"),
        ("hydroacoustics", "commercial_diving"): (0.8, "sonar imaging guides and de-risks diver work in low visibility"),
        ("hydroacoustics", "dredging_marine_civil"): (0.8, "bathymetric sonar verifies dredging volumes and seabed state"),
        ("underwater_sensors", "subsea_cable_ops"): (0.9, "sensors enable monitoring of installed subsea cables"),
        ("underwater_sensors", "iot_telematics"): (0.9, "sensor stations need telemetry to deliver data continuously"),
        ("underwater_sensors", "ai_ml"): (0.9, "sensor streams feed anomaly detection and prediction"),
        ("underwater_sensors", "dredging_marine_civil"): (0.85, "turbidity and environmental sensing is needed around dredging"),
        ("underwater_sensors", "wave_energy"): (0.8, "offshore devices need structural and environmental monitoring"),
        ("underwater_sensors", "naval_architecture"): (0.7, "a designed vessel hull hosts the sensor suite"),
        ("maritime_surveillance", "ai_ml"): (0.9, "surveillance data needs automated detection and tracking"),
        ("maritime_surveillance", "marine_navigation"): (0.75, "navigation data (AIS/radar) complements surveillance sensors"),
        ("maritime_surveillance", "naval_architecture"): (0.75, "surveillance payloads need a purpose-designed carrier vessel"),
        ("maritime_surveillance", "composite_structures"): (0.7, "lightweight platforms extend range of surveillance systems"),
        ("marine_navigation", "naval_architecture"): (0.8, "navigation systems are integrated into newly designed vessels"),
        ("marine_navigation", "underwater_vehicles"): (0.8, "unmanned vehicles depend on navigation and positioning"),
        ("marine_navigation", "cybersecurity"): (0.8, "bridge and navigation systems are safety-critical OT that must be secured"),
        ("marine_navigation", "vessel_operator"): (0.8, "vessel operators are users of navigation systems"),
        ("marine_communication", "underwater_vehicles"): (0.75, "remote vehicles need a communication link to operators"),
        ("marine_communication", "cybersecurity"): (0.8, "maritime communication links need protection"),
        ("marine_communication", "underwater_sensors"): (0.8, "sensor data needs a maritime communication path to shore"),
        ("iot_telematics", "vessel_operator"): (0.85, "fleet telematics improves control of vessel operations"),
        ("iot_telematics", "energy_grid"): (0.85, "connected devices monitor grid assets"),
        ("iot_telematics", "ai_ml"): (0.8, "telemetry becomes valuable through analytics"),
        ("iot_telematics", "wave_energy"): (0.75, "remote offshore power devices need telemetry"),
        ("iot_telematics", "water_treatment"): (0.7, "distributed treatment units benefit from remote monitoring"),
        ("iot_telematics", "cybersecurity"): (0.75, "connected devices widen the attack surface and need security"),
        ("subsea_cable_ops", "power_cables"): (1.0, "cable manufacturers need installation and repair capacity at sea"),
        ("subsea_cable_ops", "offshore_wind"): (0.95, "wind farms need array and export cable installation"),
        ("subsea_cable_ops", "wave_energy"): (0.95, "wave power plants need a subsea export cable"),
        ("subsea_cable_ops", "underwater_vehicles"): (0.9, "ROVs inspect and support cable laying and repair"),
        ("subsea_cable_ops", "ai_ml"): (0.7, "installation and inspection data can be analysed for fault prediction"),
        ("subsea_cable_ops", "visualisation_xr"): (0.65, "cable routes and seabed assets can be visualised for planning"),
        ("subsea_cable_ops", "sealing_systems"): (0.7, "cable landfalls and penetrations need sealing"),
        ("subsea_cable_ops", "commercial_diving"): (0.8, "shallow-water cable work needs divers"),
        ("power_cables", "wave_energy"): (0.85, "wave power needs dynamic power cables"),
        ("power_cables", "offshore_wind"): (0.9, "wind farms need high-voltage export cables"),
        ("power_cables", "sealing_systems"): (0.75, "cable entries need certified sealing"),
        ("power_cables", "underwater_sensors"): (0.75, "cable condition can be monitored with sensors"),
        ("wave_energy", "composite_structures"): (0.85, "lightweight composite structures reduce cost of offshore devices"),
        ("wave_energy", "naval_architecture"): (0.85, "floating energy devices need marine engineering design"),
        ("wave_energy", "commercial_diving"): (0.7, "moorings and subsea parts need underwater installation"),
        ("wave_energy", "energy_grid"): (0.75, "generated power must be integrated into the grid"),
        ("wave_energy", "testing_certification"): (0.7, "new energy devices need independent verification"),
        ("composite_structures", "underwater_vehicles"): (0.8, "composite hulls suit unmanned and underwater vehicles"),
        ("naval_architecture", "underwater_vehicles"): (0.8, "vehicle platforms need hull and system design"),
        ("naval_architecture", "embedded_systems"): (0.65, "new vessels need integrated electronics"),
        ("naval_architecture", "testing_certification"): (0.65, "vessel designs need class approval and testing"),
        ("commercial_diving", "underwater_vehicles"): (0.85, "ROVs extend or replace diver inspection"),
        ("commercial_diving", "underwater_sensors"): (0.8, "underwater works benefit from sensor-based inspection"),
        ("commercial_diving", "visualisation_xr"): (0.6, "underwater worksites can be visualised for planning and reporting"),
        ("dredging_marine_civil", "environmental_monitoring"): (0.9, "dredging permits require environmental monitoring"),
        ("dredging_marine_civil", "iot_telematics"): (0.65, "worksite equipment and sensors can be remotely monitored"),
        ("energy_grid", "ai_ml"): (0.8, "grid data supports fault prediction"),
        ("energy_grid", "cybersecurity"): (0.85, "grid control is critical infrastructure that must be secured"),
        ("energy_grid", "telecom_networks"): (0.7, "grid monitoring depends on reliable communication"),
        ("embedded_systems", "ai_ml"): (0.7, "models can be deployed on embedded devices at the edge"),
        ("embedded_systems", "underwater_vehicles"): (0.75, "vehicles need embedded control electronics"),
        ("embedded_systems", "wave_energy"): (0.65, "power devices need control electronics"),
        ("telecom_networks", "underwater_vehicles"): (0.55, "near-shore unmanned systems can use mobile networks"),
        ("telecom_networks", "iot_telematics"): (0.7, "IoT solutions run over telecom networks"),
        ("telecom_networks", "vessel_operator"): (0.6, "vessels in coastal traffic rely on mobile coverage"),
        ("visualisation_xr", "naval_architecture"): (0.65, "designs can be communicated through realistic visualisation"),
        ("visualisation_xr", "hydroacoustics"): (0.65, "sonar data can be rendered into understandable 3D scenes"),
        ("cybersecurity", "underwater_vehicles"): (0.65, "unmanned systems need secure command links"),
        ("cybersecurity", "vessel_operator"): (0.75, "ship operators must manage cyber risk on board"),
        ("system_safety", "underwater_vehicles"): (0.7, "unmanned systems need a system safety case"),
        ("system_safety", "naval_architecture"): (0.6, "complex vessels need safety and documentation work"),
        ("software_development", "underwater_sensors"): (0.6, "sensor products need data platforms and applications"),
        ("software_development", "iot_telematics"): (0.6, "IoT data needs applications to create user value"),
        ("cloud_infrastructure", "iot_telematics"): (0.65, "telemetry needs a compliant hosting platform"),
        ("cloud_infrastructure", "ai_ml"): (0.6, "models need compute and data infrastructure"),
        ("water_treatment", "environmental_monitoring"): (0.75, "treatment performance is verified by environmental monitoring"),
        ("public_maritime_authority", "maritime_surveillance"): (0.7, "authorities with a surveillance mandate are potential need owners"),
        ("public_maritime_authority", "underwater_vehicles"): (0.6, "authorities are potential need owners for unmanned systems"),
        ("public_maritime_authority", "environmental_monitoring"): (0.65, "authorities responsible for the marine environment need monitoring data"),
    }.items()
}


@dataclass(frozen=True)
class Concept:
    id: str
    title: str
    problem: str
    outcome: str
    domain: str
    slots: dict[str, tuple[str, ...]]  # slot name -> alternative capability ids
    first_experiment: str
    technical_requirements: tuple[str, ...]
    risks: tuple[str, ...] = field(default_factory=tuple)


CONCEPTS: list[Concept] = [
    Concept(
        "cable_inspection", "Autonomous subsea cable inspection and fault localisation",
        "Faults and exposure of submarine power and telecom cables are found late, and inspection depends on vessel time and manual interpretation.",
        "A repeatable inspection service combining acoustic sensing, an underwater vehicle and automated interpretation of the data.",
        "offshore_energy",
        {"Acoustic / underwater sensing": ("hydroacoustics", "underwater_sensors", "seabed_survey"),
         "Underwater vehicle": ("underwater_vehicles",),
         "Cable operations know-how": ("subsea_cable_ops", "power_cables"),
         "Automated interpretation": ("ai_ml",),
         "Data link": ("marine_communication", "iot_telematics")},
        "Record sonar and sensor data along a short, known cable section during an already planned vessel operation and test whether the cable and its burial state can be detected automatically.",
        ("Georeferenced acoustic data", "Vehicle or towed carrier", "Ground truth from cable owner", "Labelled data set"),
        ("Access to cable route data may be restricted", "Detection performance in Baltic conditions is unknown"),
    ),
    Concept(
        "env_marine_works", "Real-time environmental monitoring for dredging and marine construction",
        "Dredging and underwater construction must document turbidity and environmental impact, usually with manual sampling.",
        "A connected monitoring kit that gives contractors and authorities continuous, documented environmental data around a worksite.",
        "marine_environment",
        {"Environmental / underwater sensing": ("underwater_sensors", "environmental_monitoring", "hydroacoustics"),
         "Marine works": ("dredging_marine_civil", "commercial_diving"),
         "Telemetry": ("iot_telematics", "marine_communication"),
         "Analytics": ("ai_ml",)},
        "Deploy two sensor points at one ongoing dredging site for two weeks and compare the continuous series with the manual samples already required by the permit.",
        ("Turbidity and position sensing", "Telemetry from the worksite", "Permit reference values"),
        ("Regulatory acceptance of continuous data is not confirmed", "Sensor fouling"),
    ),
    Concept(
        "autonomous_surveillance", "Autonomous maritime surveillance and vessel tracking system",
        "Continuous surveillance of large sea areas is personnel-intensive and leaves gaps.",
        "A demonstrator in which an unmanned or lightweight platform carries surveillance sensors and reports detections automatically.",
        "maritime_surveillance",
        {"Surveillance sensing": ("maritime_surveillance", "hydroacoustics", "underwater_sensors"),
         "Navigation": ("marine_navigation",),
         "Platform design": ("naval_architecture", "composite_structures", "underwater_vehicles"),
         "Detection & tracking": ("ai_ml",),
         "Secure communication": ("marine_communication", "cybersecurity", "telecom_networks")},
        "Mount an existing sensor on a manned work boat and run a one-day trial measuring detection range and data-link availability on a defined test area.",
        ("Sensor payload", "Carrier platform", "Navigation data", "Secure link", "Reference tracks (e.g. AIS)"),
        ("Export-control and security restrictions may apply", "Autonomy regulations at sea"),
    ),
    Concept(
        "offshore_asset_monitoring", "Condition monitoring of offshore power assets",
        "Wave and wind power devices and their cables are hard to reach, so unplanned failures are expensive.",
        "A monitoring concept that connects sensors on offshore power assets to shore and predicts maintenance needs.",
        "offshore_energy",
        {"Energy asset": ("wave_energy", "offshore_wind", "power_cables"),
         "Sensing": ("underwater_sensors", "hydroacoustics"),
         "Telemetry": ("iot_telematics", "marine_communication"),
         "Offshore maintenance": ("subsea_cable_ops", "commercial_diving"),
         "Prediction": ("ai_ml",)},
        "Instrument one component on a test rig or prototype with two sensors and a telemetry link for one month and review the data with the asset owner.",
        ("Asset access", "Sensors rated for the environment", "Telemetry", "Failure-mode knowledge"),
        ("Too few failures to train models", "Power and bandwidth budget offshore"),
    ),
    Concept(
        "wave_power_cabling", "Installation and cabling concept for wave power arrays",
        "Wave power needs low-cost electrical connection and installation methods to reach commercial scale.",
        "A joint installation concept covering dynamic cable, sealing, structure design and marine installation.",
        "offshore_energy",
        {"Wave energy device": ("wave_energy",),
         "Power cable": ("power_cables",),
         "Marine installation": ("subsea_cable_ops", "commercial_diving"),
         "Structure design": ("composite_structures", "naval_architecture"),
         "Sealing": ("sealing_systems",)},
        "Run a joint desk study for one reference site that defines the cable interface, the installation sequence and the cost drivers.",
        ("Device interface specification", "Site data", "Installation vessel capability"),
        ("Device developer's roadmap and site are not public", "Cost model uncertainty"),
    ),
    Concept(
        "connected_fleet", "Secure connected-vessel operations platform",
        "Smaller vessel operators lack an integrated, secure view of position, equipment status and communication.",
        "A fleet platform that combines telematics, navigation data and secure hosting for work boats and ferries.",
        "vessel_operations",
        {"Telematics": ("iot_telematics",),
         "Navigation & on-board systems": ("marine_navigation", "marine_communication"),
         "Vessel operator": ("vessel_operator",),
         "Security": ("cybersecurity",),
         "Software & hosting": ("software_development", "cloud_infrastructure")},
        "Connect one vessel for four weeks and review with its crew which three data points actually change decisions.",
        ("On-board data interfaces", "Connectivity", "Hosting", "Operator participation"),
        ("Integration with legacy bridge equipment", "Willingness to share operational data"),
    ),
    Concept(
        "grid_fault_detection", "Predictive fault detection for local energy grids",
        "Grid operators detect many faults only after an outage.",
        "Analytics on connected grid sensors that warns about developing faults.",
        "smart_grid",
        {"Grid operator / monitoring": ("energy_grid",),
         "Connected devices": ("iot_telematics", "embedded_systems"),
         "Analytics": ("ai_ml",),
         "Communication": ("telecom_networks",),
         "Security": ("cybersecurity",)},
        "Analyse one year of existing fault and measurement records from one substation area to test whether precursors are visible.",
        ("Historic measurement data", "Fault logs", "Secure data sharing agreement"),
        ("Data access and confidentiality", "Rare events"),
    ),
    Concept(
        "subsea_digital_twin", "Visual digital twin of subsea worksites and assets",
        "Stakeholders cannot see what is on the seabed, which slows planning, permitting and reporting.",
        "A 3D representation of subsea assets built from survey data, used for planning and communication.",
        "offshore_energy",
        {"Survey data": ("hydroacoustics", "seabed_survey"),
         "Visualisation": ("visualisation_xr",),
         "Subsea operations": ("subsea_cable_ops", "commercial_diving", "dredging_marine_civil"),
         "Software platform": ("software_development", "cloud_infrastructure")},
        "Turn one existing survey data set from a completed project into an interactive 3D scene and test it with the project owner.",
        ("Survey data with usage rights", "3D pipeline", "Hosting"),
        ("Data ownership", "Accuracy expectations versus visual impression"),
    ),
    Concept(
        "remote_underwater_inspection", "Remote inspection support for underwater construction",
        "Inspection of quays and underwater structures relies on divers in poor visibility.",
        "A combination of vehicle, sensor and communication that lets engineers on shore follow and document inspections.",
        "coastal_infrastructure",
        {"Underwater works": ("commercial_diving", "dredging_marine_civil"),
         "Vehicle": ("underwater_vehicles",),
         "Sensing": ("hydroacoustics", "underwater_sensors"),
         "Communication": ("marine_communication", "iot_telematics"),
         "Documentation": ("visualisation_xr", "software_development")},
        "Shadow one planned diver inspection with a sensor or small vehicle and compare the documentation quality.",
        ("Inspection site", "Vehicle or sensor", "Topside link"),
        ("Visibility and current conditions", "Work-environment regulations for diving"),
    ),
    Concept(
        "lightweight_usv", "Lightweight unmanned survey vessel",
        "Survey and monitoring tasks use crewed vessels that are costly for routine work.",
        "A lightweight unmanned surface vessel concept with integrated navigation, sensing and control electronics.",
        "autonomous_maritime",
        {"Hull & structure": ("naval_architecture", "composite_structures"),
         "Navigation": ("marine_navigation",),
         "Survey payload": ("hydroacoustics", "underwater_sensors"),
         "Control electronics": ("embedded_systems",),
         "Safety case": ("system_safety", "testing_certification")},
        "Produce a concept design and payload budget for one defined survey mission and review it against class and authority requirements.",
        ("Mission profile", "Payload weight and power budget", "Regulatory route"),
        ("Regulatory route for unmanned operation", "Business case versus existing vessels"),
    ),
    Concept(
        "secure_maritime_ot", "Verified cyber-secure maritime on-board systems",
        "Navigation and communication systems on vessels are increasingly connected and exposed to cyber risk.",
        "A tested reference configuration and assessment method for on-board operational technology.",
        "vessel_operations",
        {"On-board systems": ("marine_navigation", "marine_communication"),
         "Cybersecurity": ("cybersecurity",),
         "Verification": ("testing_certification", "system_safety"),
         "Operator / platform": ("vessel_operator", "naval_defence_systems")},
        "Run a structured cyber-risk assessment on one representative bridge system in a lab setup.",
        ("Representative equipment", "Assessment method", "Lab environment"),
        ("Vendor access to equipment internals", "Regulatory requirements differ by vessel type"),
    ),
]

CONCEPTS_BY_ID = {c.id: c for c in CONCEPTS}


def detect_capabilities(text: str) -> list[tuple[str, str]]:
    """Return [(capability_id, matched_term)] for every taxonomy capability mentioned in text."""
    found = []
    for cid, pat in _PATTERNS.items():
        m = pat.search(text or "")
        if m:
            found.append((cid, m.group(0)))
    return found


def relation(cap_a: str, cap_b: str) -> tuple[float, str, str] | None:
    """Return (weight, rationale, kind) for a complementary relation between two different capabilities.

    kind is "explicit" (capability-level) or "role" (generic value-chain relation).
    Returns None when no relation is defined: different technologies are NOT assumed complementary.
    """
    if cap_a == cap_b or cap_a not in CAPABILITIES or cap_b not in CAPABILITIES:
        return None
    hit = CAPABILITY_RELATIONS.get(frozenset((cap_a, cap_b)))
    if hit:
        return hit[0], hit[1], "explicit"
    ra, rb = CAPABILITIES[cap_a].role, CAPABILITIES[cap_b].role
    for src, dst in ((ra, rb), (rb, ra)):
        hit = ROLE_RELATIONS.get((src, dst))
        if hit:
            # generic relations are weaker evidence of fit than explicit ones
            return hit[0] * 0.6, hit[1], "role"
    return None


def shared_domains(cap_a: str, cap_b: str) -> list[str]:
    return sorted(set(CAPABILITIES[cap_a].domains) & set(CAPABILITIES[cap_b].domains))
