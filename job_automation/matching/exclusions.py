from __future__ import annotations

import re

from database.models import Job


# Pay/currency markers that betray a low-cost-region listing (e.g. a "Spain"
# posting that actually pays 100,000 PKR/month). Word-bounded so "inr"/"pkr"
# never match inside an unrelated word.
_CURRENCY_PATTERNS = [
    r"\bpkr\b",          # Pakistani rupee
    r"\binr\b",          # Indian rupee
    r"₨",           # ₨ rupee sign
    r"₹",           # ₹ Indian rupee sign
    r"\brupees?\b",
    r"\blakhs?\b",       # Indian "lakh" (100,000)
    r"\bcrores?\b",      # Indian "crore" (10,000,000)
    r"\brs\.?\s?\d",     # "Rs 100000", "Rs. 1,00,000"
]

# India/Pakistan country, demonym and major-city names. Word boundaries keep
# "india" from matching "Indiana"/"Indianapolis" and "indore" from "indoor".
_BANNED_PLACES = [
    "india", "indian", "pakistan", "pakistani",
    # India
    "mumbai", "delhi", "new delhi", "bangalore", "bengaluru", "hyderabad",
    "chennai", "kolkata", "pune", "ahmedabad", "gurgaon", "gurugram", "noida",
    "jaipur", "lucknow", "kanpur", "nagpur", "indore", "coimbatore", "kochi",
    "thiruvananthapuram", "chandigarh", "mysore", "mysuru",
    # Pakistan
    "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad", "peshawar",
    "multan", "quetta", "sialkot", "gujranwala",
]

_CURRENCY_RE = re.compile("|".join(_CURRENCY_PATTERNS))
_PLACE_RE = re.compile(r"\b(?:" + "|".join(re.escape(place) for place in _BANNED_PLACES) + r")\b")


def excluded_low_cost_region(job: Job) -> tuple[bool, str]:
    """True when a posting should be banned as an India/Pakistan low-cost listing.

    Two independent signals trigger a ban:
      * the pay is quoted in PKR/INR (rupees/lakh/crore), or
      * the posting names India, Pakistan or one of their major cities.

    Either is enough -- a remote "Spain" role that pays in PKR is still banned.
    Returns ``(excluded, reason)`` so the pipeline can log why a job was dropped.
    """
    blob = f"{job.salary or ''}\n{job.location or ''}\n{job.text_blob()}".lower()
    if _CURRENCY_RE.search(blob):
        return True, "pay quoted in PKR/INR (rupees/lakh/crore)"
    if _PLACE_RE.search(blob):
        return True, "India/Pakistan location"
    return False, ""
