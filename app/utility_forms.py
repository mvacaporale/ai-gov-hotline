# Standard library imports
import os
from typing import Optional
from datetime import date, datetime

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

    # The follow fields will be prompted from the user.
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
        default=None, description="Resident's date of birth in MM/DD/YYYY format"
    )
    phone_number: Optional[str] = Field(
        default=None, description="Phone number of the resident."
    )
    email_address: Optional[str] = Field(
        default=None, description="Resident's email address"
    )

    # Automatically fill in today's date/
    date: str = Field(
        default=date.today().strftime("%m/%d/%Y"), description="Today's date"
    )

    # Store the parsed components after validation
    residence_address: Optional[str] = None  # line one on the pdf
    mailing_address: Optional[str] = None  # line two on the pdf
    parsed_city: Optional[str] = None
    parsed_state: Optional[str] = None
    parsed_zip: Optional[str] = None
    parsed_country: Optional[str] = None

    # Compose the full user name when we have their first and last
    customer_name: Optional[str] = None

    def update(self, **kwargs):
        """
        The update manually runs the `validate_and_complete_address` function
        which allows us to simultaneously update the parse address information.
        The safest way to add values to this form is through this function.
        """
        print("updating w/ keyword args: ", kwargs)

    
        if "address_input" in kwargs:
            address_fields = self.validate_and_complete_address(kwargs["address_input"])
            kwargs = kwargs | address_fields  # Update with the completed address.

        # Combine the first and the last name for the full name.
        if "first_name" in kwargs or "last_name" in kwargs:

            first_name = kwargs.get("first_name", None) or getattr(self, "first_name", None)
            last_name = kwargs.get("last_name", None) or getattr(self, "last_name", None)

            print("combining first and last", first_name, last_name)
            print("first_name is not None and last_name is not None", first_name is not None, last_name is not None)

            if first_name is not None and last_name is not None:
                kwargs.update({"customer_name": f"{first_name} {last_name}"})

        self.__class__.model_validate(self.__dict__ | kwargs)
        self.__dict__.update(kwargs)

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

    @field_validator("date_of_birth")
    def validate_birthday(cls, value):
    
        if value is None:
            return None
    
        try:
            # Try to parse the date string
            date = datetime.strptime(value, "%m/%d/%Y")

            # Check if the date is not in the future
            if date > datetime.now():
                raise ValueError("Birthday cannot be in the future")

            # Check if the year is reasonable (e.g., not before 1900)
            if date.year < 1900:
                raise ValueError("Birthday year must be 1900 or later")

            # Return the original string if all validation passes
            return value

        except ValueError as e:
            if "does not match format" in str(e):
                raise ValueError("Birthday must be in mm/dd/yyyy format")
            raise e

    def validate_and_complete_address(self, value: str) -> dict:
        """
        This will validate the address given and use Google's API to complete
        the address. Note: Because this function also aims to save the parsed
        address information we can't use the `field_validator` decorator. 
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
            city = parsed["locality"]
            state = parsed["administrative_area_level_1"]
            zip_code = parsed["postal_code"]
            address_fields = {
                "residence_address": f"{parsed['street_number']} {parsed['route']}".strip(),
                "mailing_address": f"{city}, {state} {zip_code}", 
                "parsed_city": city,
                "parsed_state": state,
                "parsed_zip": zip_code,
                "parsed_country": "US",
            }

            return address_fields

        except ApiError as e:
            raise ValueError(f"Address validation failed: {str(e)}")
