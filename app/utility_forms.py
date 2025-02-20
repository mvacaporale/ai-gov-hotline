# Standard library imports
import os
from typing import Optional
from datetime import date

# Third party imports
from dotenv import load_dotenv
from pydantic import Field
from pydantic import BaseModel
from pydantic import field_validator
from googlemaps import Client
from googlemaps.exceptions import ApiError


load_dotenv(dotenv_path=".env.local")

# Standard library imports
import re


class UtilityAssistanceApplication(BaseModel):
    """
    Model for a Wake County Utility Assistance Application.
    """

    first_name: Optional[str] = Field(
        default=None, description="First name of the resident"
    )
    last_name: Optional[str] = Field(
        default=None, description="Last name of the resident"
    )
    address_input: Optional[str] = Field(
        default=None, description="Street address of the resident."
    )
    date_of_birth: Optional[str] = Field(
        default=None, description="Resident's date of birth in YYYY-MM-DD format"
    )
    phone_number: Optional[str] = Field(
        default=None, description="Phone number of the resident."
    )
    email_address: Optional[str] = Field(
        default=None, description="Resident's email address"
    )

    work_first_benefits: Optional[str] = Field(
        default=None,
        description="Whether or not anyone in the house is receiving work first benefits. Answer should be yes or no.",
        enum=["yes", "no"],
    )

    date: str = Field(
        default=date.today().strftime("%m/%d/%Y"), description="Today's date"
    )

    # Store the parsed components after validation
    residence_address: Optional[str] = None
    parsed_city: Optional[str] = None
    parsed_state: Optional[str] = None
    parsed_zip: Optional[str] = None
    parsed_country: Optional[str] = None

    def update(self, **kwargs):
        """
        The update manually runs the `validate_and_complete_address` function
        which allows us to simultaneously update the parse address information.
        """
        if "address_input" in kwargs:
            address_fields = self.validate_and_complete_address(kwargs["address_input"])
        else:
            address_fields = {}

        self.__class__.model_validate(self.__dict__ | kwargs | address_fields)
        self.__dict__.update(kwargs | address_fields)

    @field_validator("phone_number")
    def validate_phone(cls, value: str) -> str:

        if value is None:
            return None

        # Remove any spaces, dashes, or parentheses
        cleaned = re.sub(r"[\s\-\(\)]", "", value)

        # Check if it matches E.164 format
        if not re.match(r"^\+?1?\d{9,15}$", cleaned):
            raise ValueError("Invalid international phone number")

        return cleaned

    @field_validator("email_address")
    def validate_email(cls, value: str) -> str:

        if value is None:
            return None

        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, value):
            raise ValueError("Invalid email format")

        # Optional: Convert to lowercase for consistency
        return value.lower()

    def validate_and_complete_address(self, value: str) -> dict:
        """
        This will validate the address given and use Google's API to complete
        the address.
        """

        if value is None:
            return {}

        gmaps = Client(key=os.getenv("GOOGLE_API_KEY"))

        try:
            # Get place predictions
            places_result = gmaps.places_autocomplete(
                value, types=["address"], components={"country": ["us"]}
            )

            if not places_result:
                raise ValueError("No matching addresses found")

            # Get details for the first (most likely) result
            place_id = places_result[0]["place_id"]
            place_details = gmaps.place(place_id)["result"]

            # Parse address components
            address_components = place_details["address_components"]
            parsed = {
                "street_number": "",
                "route": "",
                "locality": "",
                "administrative_area_level_1": "",
                "postal_code": "",
            }

            for component in address_components:
                for type in component["types"]:
                    if type in parsed:
                        parsed[type] = component["long_name"]

            # Update the model fields using info.data
            address_fields = {
                "residence_address": f"{parsed['street_number']} {parsed['route']}".strip(),
                "parsed_city": parsed["locality"],
                "parsed_state": parsed["administrative_area_level_1"],
                "parsed_zip": parsed["postal_code"],
                "parsed_country": "US",
            }

            return address_fields

        except ApiError as e:
            raise ValueError(f"Address validation failed: {str(e)}")
