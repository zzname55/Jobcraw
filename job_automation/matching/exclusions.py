from __future__ import annotations

import re

from database.models import Job


# Pay/currency markers that betray a low-wage-region listing (e.g. a "Spain"
# posting that actually pays 100,000 PKR/month). ISO codes and local terms are
# word-bounded so "inr"/"pkr" never match inside an unrelated word.
#
# NOTE: the Philippine peso code "PHP" is deliberately NOT listed -- it collides
# with the PHP programming language and would nuke legitimate tech jobs. The
# Philippines are caught via the ₱ symbol and city/country names below instead.
# "peso"/"dong"/"shilling"/"baht" are likewise omitted (too many collisions).
_CURRENCY_PATTERNS = [
    r"\bpkr\b",   # Pakistan rupee
    r"\binr\b",   # India rupee
    r"\bbdt\b",   # Bangladesh taka
    r"\bngn\b",   # Nigeria naira
    r"\blkr\b",   # Sri Lanka rupee
    r"\bnpr\b",   # Nepal rupee
    r"\bidr\b",   # Indonesia rupiah
    r"\bvnd\b",   # Vietnam dong
    r"\begp\b",   # Egypt pound
    r"\bkes\b",   # Kenya shilling
    r"\bghs\b",   # Ghana cedi
    "₨", "₹", "৳", "₦", "₱", "₫",  # rupee / taka / naira / peso / dong signs
    r"\brupees?\b",
    r"\blakhs?\b",    # Indian "lakh" (100,000)
    r"\bcrores?\b",   # Indian "crore" (10,000,000)
    r"\bnaira\b",
    r"\btaka\b",
    r"\brupiah\b",
    r"\bcedi\b",
    r"\brs\.?\s?\d",  # "Rs 100000", "Rs. 1,00,000"
]

# Low-wage-region country, demonym and major-city names. Word boundaries keep
# "india" from matching "Indiana"/"Indianapolis" and "indore" from "indoor".
# Ambiguous city names that collide with higher-wage places are intentionally
# left out (Lagos -> also Portugal, Alexandria -> also USA, Kochi -> also Japan);
# the country/demonym token still catches those postings.
_BANNED_PLACES = [
    # India
    "india", "indian", "mumbai", "delhi", "new delhi", "bangalore", "bengaluru",
    "hyderabad", "chennai", "kolkata", "pune", "ahmedabad", "gurgaon", "gurugram",
    "noida", "jaipur", "lucknow", "kanpur", "nagpur", "indore", "coimbatore",
    "chandigarh", "mysore", "mysuru", "thiruvananthapuram",
    # Pakistan
    "pakistan", "pakistani", "karachi", "lahore", "islamabad", "rawalpindi",
    "faisalabad", "peshawar", "multan", "quetta", "sialkot", "gujranwala",
    # Bangladesh
    "bangladesh", "bangladeshi", "dhaka", "chittagong", "chattogram",
    # Sri Lanka
    "sri lanka", "sri lankan", "colombo",
    # Nepal
    "nepal", "nepali", "nepalese", "kathmandu",
    # Philippines
    "philippines", "philippine", "filipino", "filipina", "manila", "cebu",
    "makati", "davao", "quezon city",
    # Indonesia
    "indonesia", "indonesian", "jakarta", "surabaya", "bandung",
    # Vietnam
    "vietnam", "vietnamese", "hanoi", "ho chi minh", "saigon", "da nang",
    # Nigeria
    "nigeria", "nigerian", "abuja", "ibadan",
    # Kenya
    "kenya", "kenyan", "nairobi", "mombasa",
    # Ghana
    "ghana", "ghanaian", "accra", "kumasi",
    # Egypt
    "egypt", "egyptian", "cairo", "giza",
]

_CURRENCY_RE = re.compile("|".join(_CURRENCY_PATTERNS))
_PLACE_RE = re.compile(r"\b(?:" + "|".join(re.escape(place) for place in _BANNED_PLACES) + r")\b")


def excluded_low_cost_region(job: Job) -> tuple[bool, str]:
    """True when a posting should be banned as a low-wage-region listing.

    Two independent signals trigger a ban:
      * the pay is quoted in a low-wage-region currency (PKR/INR/BDT/NGN/... or
        rupees/lakh/crore/naira/taka/...), or
      * the posting names one of the banned low-wage countries or a major city.

    Either is enough -- a remote "Spain" role that pays in PKR is still banned.
    Returns ``(excluded, reason)`` so the pipeline can log why a job was dropped.
    """
    blob = f"{job.salary or ''}\n{job.location or ''}\n{job.text_blob()}".lower()
    match = _CURRENCY_RE.search(blob)
    if match:
        return True, f"low-wage-region pay ({match.group(0).strip()})"
    match = _PLACE_RE.search(blob)
    if match:
        return True, f"low-wage region ({match.group(0).strip()})"
    return False, ""
