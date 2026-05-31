"""Default sizing filters for deal discovery (mens medium apparel, mens US 11 shoes)."""

APPAREL_SIZE = "M"
SHOE_SIZE_US = "11"
# Foot-store slugs commonly use EU sizing; US mens 11 ≈ EU 45.
SHOE_SIZE_EU = "45"

# Required eBay Browse API search strings (NWT/BIN filters applied in ebay_source).
EBAY_APPAREL_QUERY = "Mizuno medium mens NWT"
EBAY_SHOE_QUERY = "Mens Mizuno size 11 new"
