from pathlib import Path
import time
from typing import Any, Optional, Callable, Mapping
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from lavague.core.base_driver import BaseDriver
from PIL import Image
from io import BytesIO
from selenium.webdriver.chrome.options import Options
from lavague.core.utilities.format_utils import (
    return_assigned_variables,
    keep_assignments,
    extract_code_from_funct,
)


class SeleniumDriver(BaseDriver):
    driver: WebDriver

    def __init__(
        self,
        url: Optional[str] = None,
        get_selenium_driver: Optional[Callable[[], WebDriver]] = None,
        headless: bool = True,
        user_data_dir: Optional[str] = None,
        width: int = 1080,
        height: int = 1080,
        no_load_strategy: bool = False,
        options: Optional[Options] = None,
    ):
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.width = width
        self.height = height
        self.no_load_strategy = no_load_strategy
        self.options = options
        super().__init__(url, get_selenium_driver)

    #   Default code to init the driver.
    #   Before making any change to this, make sure it is compatible with code_for_init, which parses the code of this function
    #   These imports are necessary as they will be pasted to the output
    def default_init_code(self) -> Any:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains

        if self.options:
            chrome_options = self.options
        else:
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless")
            if self.user_data_dir:
                chrome_options.add_argument(f"--user-data-dir={self.user_data_dir}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.page_load_strategy = (
                "normal" if self.no_load_strategy is False else "none"
            )

        driver = webdriver.Chrome(options=chrome_options)
        self.driver = driver
        self.resize_driver(self.width, self.height)
        return self.driver

    def code_for_init(self) -> str:
        init_lines = extract_code_from_funct(self.init_function)
        code_lines = []
        keep_next = True
        for line in init_lines:
            if "--user-data-dir" in line:
                line = line.replace(
                    f"{{self.user_data_dir}}", f'"{self.user_data_dir}"'
                )
            if "if" in line:
                if ("headless" in line and not self.headless) or (
                    "user_data_dir" in line and self.user_data_dir is None
                ):
                    keep_next = False
            elif keep_next:
                if "self" not in line:
                    code_lines.append(line.strip())
            else:
                keep_next = True
        code_lines.append(self.code_for_resize(self.width, self.height))
        return "\n".join(code_lines) + "\n"

    def get_driver(self) -> WebDriver:
        return self.driver

    def resize_driver(self, width, height) -> None:
        # Selenium is only being able to set window size and not viewport size
        self.driver.set_window_size(width, height)
        viewport_height = self.driver.execute_script("return window.innerHeight;")

        height_difference = height - viewport_height
        self.driver.set_window_size(width, height + height_difference)
        self.width = width
        self.height = height

    def code_for_resize(self, width, height) -> str:
        return f"""
driver.set_window_size({width}, {height})
viewport_height = driver.execute_script("return window.innerHeight;")
height_difference = {height} - viewport_height
driver.set_window_size({width}, {height} + height_difference)
"""

    def get_url(self) -> Optional[str]:
        if self.driver.current_url == "data:,":
            return None
        return self.driver.current_url

    def code_for_get(self, url: str) -> str:
        return f'driver.get("{url}")'

    def get(self, url: str) -> None:
        self.driver.get(url)

    def back(self) -> None:
        self.driver.back()

    def code_for_back(self) -> None:
        return "driver.back()"

    def get_html(self) -> str:
        return self.driver.page_source

    def get_screenshot_as_png(self) -> bytes:
        return self.driver.get_screenshot_as_png()

    def destroy(self) -> None:
        self.driver.quit()

    def maximize_window(self) -> None:
        self.driver.maximize_window()

    def check_visibility(self, xpath: str) -> bool:
        try:
            return self.driver.find_element(By.XPATH, xpath).is_displayed()
        except:
            return False

    def get_highlighted_element(self, generated_code: str):
        local_scope = {"driver": self.get_driver()}
        assignment_code = keep_assignments(generated_code)
        self.exec_code(assignment_code, locals=local_scope)

        # We extract pairs of variables assigned during execution with their name and pointer
        variable_names = return_assigned_variables(generated_code)

        elements = []

        for variable_name in variable_names:
            var = local_scope[variable_name]
            if type(var) == WebElement:
                elements.append(var)

        if len(elements) == 0:
            raise ValueError(f"No element found.")

        outputs = []
        for element in elements:
            element: WebElement

            bounding_box = {}
            viewport_size = {}

            self.execute_script(
                "arguments[0].setAttribute('style', arguments[1]);",
                element,
                "border: 2px solid red;",
            )
            self.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", element
            )
            screenshot = self.get_screenshot_as_png()

            bounding_box["x1"] = element.location["x"]
            bounding_box["y1"] = element.location["y"]
            bounding_box["x2"] = bounding_box["x1"] + element.size["width"]
            bounding_box["y2"] = bounding_box["y1"] + element.size["height"]

            viewport_size["width"] = self.execute_script("return window.innerWidth;")
            viewport_size["height"] = self.execute_script("return window.innerHeight;")
            screenshot = BytesIO(screenshot)
            screenshot = Image.open(screenshot)
            output = {
                "screenshot": screenshot,
                "bounding_box": bounding_box,
                "viewport_size": viewport_size,
            }
            outputs.append(output)
        return outputs

    def exec_code(
        self,
        code: str,
        globals: dict[str, Any] = None,
        locals: Mapping[str, object] = None,
    ):
        exec(self.import_lines)
        driver = self.driver
        exec(code, globals, locals)

    def execute_script(self, js_code: str, *args) -> Any:
        return self.driver.execute_script(js_code, *args)

    def scroll_up(self):
        self.execute_script("window.scrollBy(0, -window.innerHeight);")

    def scroll_down(self):
        self.execute_script("window.scrollBy(0, window.innerHeight);")

    def code_for_execute_script(self, js_code: str, *args) -> str:
        return (
            f"driver.execute_script({js_code}, {', '.join(str(arg) for arg in args)})"
        )

    def resize_driver(self, width, targeted_height):
        """Resize the Selenium driver viewport to a targeted height and width.
        This is due to Selenium only being able to set window size and not viewport size.
        """
        self.driver.set_window_size(width, targeted_height)

        viewport_height = self.driver.execute_script("return window.innerHeight;")

        height_difference = targeted_height - viewport_height
        self.driver.set_window_size(width, targeted_height + height_difference)

    def get_capability(self) -> str:
        return SELENIUM_PROMPT_TEMPLATE


SELENIUM_PROMPT_TEMPLATE = """
You are a Selenium expert in writing code to interact with web pages. You have been given a series of HTML snippets and queries.
Your goal is to write Selenium code to answer queries. Your answer must be a Python markdown only.
Always target elements by XPATH.

Provide high level explanations about why you think this element is the right one.
Your answer must be short and concise. 

Here are examples of previous answers:

HTML:
<div class="QS5gu ud1jmf" role="none" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[1]/div/div/button/div">Inloggen</div></button></div></div></div><div class="GZ7xNe" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]"><h1 class="I90TVb" id="S3BnEe" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/h1">Voordat je verdergaat naar Google</h1><div class="AG96lb" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div"><div class="eLZYyf" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[1]">We gebruiken <a class="F4a1l" href="https://policies.google.com/technologies/cookies?utm_source=ucbs&amp;hl=nl" target="_blank" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[1]/a">cookies</a> en gegevens voor het volgende:<ul class="dbXO9" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[1]/ul"><li class="gowsYd ibCF0c" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[1]/ul/li[1]">Google-services leveren en onderhouden</li><li class="gowsYd GwwhGf" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[1]/ul/li[2]">Uitval bijhouden en bescherming bieden tegen spam, fraude en misbruik</li><li class="gowsYd v8Bpfb" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[1]/ul/li[3]">Doelgroepbetrokkenheid en sitestatistieken meten om inzicht te krijgen in hoe onze services worden gebruikt en de kwaliteit van die services te verbeteren</li></ul></div><div class="eLZYyf" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[2]">Als je Alles accepteren kiest, gebruiken we cookies en gegevens ook voor het volgende:<ul class="dbXO9" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[2]/ul"><li class="gowsYd M6j9qf" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[2]/ul/li[1]">Nieuwe services ontwikkelen en verbeteren</li><li class="gowsYd v8Bpfb" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[2]/ul/li[2]">Advertenties laten zien en de effectiviteit ervan meten</li><li class="gowsYd e21Mac" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[2]/ul/li[3]">Gepersonaliseerde content laten zien (afhankelijk van je instellingen)</li><li class="gowsYd ohEWPc" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[2]/ul/li[4]">Gepersonaliseerde advertenties laten zien (afhankelijk van je instellingen)</li></ul><div class="jLhwdc" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[2]/div">Als je Alles afwijzen kiest, gebruiken we cookies niet voor deze aanvullende doeleinden.</div></div><div class="yS1nld" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[3]">Niet-gepersonaliseerde content wordt beïnvloed door factoren zoals de content die je op dat moment bekijkt, activiteit in je actieve zoeksessie en je locatie. Niet-gepersonaliseerde advertenties worden beïnvloed door de content die je op dat moment bekijkt en je algemene locatie. Gepersonaliseerde content en advertenties kunnen ook relevantere resultaten, aanbevelingen en op jou toegespitste advertenties omvatten die zijn gebaseerd op eerdere activiteit van deze browser, zoals uitgevoerde Google-zoekopdrachten. We gebruiken cookies en gegevens ook om te zorgen dat de functionaliteit geschikt is voor je leeftijd, als dit relevant is.</div><div class="yS1nld" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[4]">Selecteer Meer opties om meer informatie te bekijken, waaronder over hoe je je privacyinstellingen beheert. Je kunt ook altijd naar <span xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[2]/div/div[4]/span">g.co/privacytools</span> gaan.</div></div></div><div class="spoKVd" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]">
<div class="spoKVd" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]"><div class="GzLjMd" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]"><button class="tHlp8d" data-ved="0ahUKEwjX3bmBmKeGAxU2xQIHHcGoAg4Q4cIICHw" id="W0wltc" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[1]"><div class="QS5gu sy4vM" role="none" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[1]/div">Alles afwijzen</div></button><button class="tHlp8d" data-ved="0ahUKEwjX3bmBmKeGAxU2xQIHHcGoAg4QiZAHCH0" id="L2AGLb" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[2]"><div class="QS5gu sy4vM" role="none" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[2]/div">Alles accepteren</div></button></div><div class="GzLjMd" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[2]"><button class="tHlp8d" data-ved="0ahUKEwjX3bmBmKeGAxU2xQIHHcGoAg4QiJAHCH4" id="VnjCcb" role="link" tabindex="-1" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[2]/button"><a class="eOjPIe" tabindex="0" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[2]/button/a">Meer opties</a></button></div></div><div class="XWlrff cG0Dmf" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[4]"><a class="peRL2e" data-ved="0ahUKEwjX3bmBmKeGAxU2xQIHHcGoAg4Qj5AHCH8" href="https://policies.google.com/privacy?hl=nl&amp;fg=1&amp;utm_source=ucbs" id="RP3V5c" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[4]/a[1]">Privacy</a>
<div class="spoKVd" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]"><div class="GzLjMd" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]"><button class="tHlp8d" data-ved="0ahUKEwjX3bmBmKeGAxU2xQIHHcGoAg4Q4cIICHw" id="W0wltc" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[1]"><div class="QS5gu sy4vM" role="none" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[1]/div">Alles afwijzen</div></button><button class="tHlp8d" data-ved="0ahUKEwjX3bmBmKeGAxU2xQIHHcGoAg4QiZAHCH0" id="L2AGLb" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[2]"><div class="QS5gu sy4vM" role="none" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[2]/div">Alles accepteren</div></button></div><div class="GzLjMd" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[2]"><button class="tHlp8d" data-ved="0ahUKEwjX3bmBmKeGAxU2xQIHHcGoAg4QiJAHCH4" id="VnjCcb" role="link" tabindex="-1" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[2]/button"><a class="eOjPIe" tabindex="0" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[2]/button/a">Meer opties</a></button></div></div><div class="XWlrff cG0Dmf" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[4]"><a class="peRL2e" data-ved="0ahUKEwjX3bmBmKeGAxU2xQIHHcGoAg4Qj5AHCH8" href="https://policies.google.com/privacy?hl=nl&amp;fg=1&amp;utm_source=ucbs" id="RP3V5c" xpath="/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[4]/a[1]">Privacy</a>
Query: Click on the button labeled 'Alles accepteren' to accept all cookies.
Completion:
```python
# Let's think step by step

# First, we notice that the query asks us to click on the button labeled 'Alles accepteren' to accept all cookies.

# In the provided HTML, we can see several button elements.

# We need to identify the correct button labeled 'Alles accepteren'.

# Upon examining the HTML structure, we see that the button with the text 'Alles accepteren' is located within a specific hierarchy.

# We need to navigate through the hierarchy to accurately locate this button.

# The correct button is located within a div element with a specific class and role attribute, which helps us ensure that we are targeting the right element.

# Specifically, for 'Alles accepteren', there is a button element with a unique ID 'L2AGLb' which contains a div with the text 'Alles accepteren'.

# We observe that this button element has the following XPath:
# /html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[2]

# Thus, we believe this is the correct element to be interacted with:
accept_all_button = driver.find_element(By.XPATH, "/html/body/div[2]/div[2]/div[3]/span/div/div/div/div[3]/div[1]/button[2]")

# Then we can click on the button
accept_all_button.click()
```
---
HTML:
<div class="devsite-top-logo-row-middle" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]">
<div class="devsite-header-upper-tabs" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]">
<devsite-tabs class="upper-tabs devsite-overflow-menu--open" connected="" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs">
<nav aria-label="Upper tabs" class="devsite-tabs-wrapper" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav">
<tab class="devsite-active" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[1]">
<a aria-label="Gemini API, selected" class="devsite-tabs-content gc-analytics-event" data-category="Site-Wide Custom Events" data-label="Tab: Gemini API" href="https://ai.google.dev/gemini-api" track-metadata-eventdetail="https://ai.google.dev/gemini-api" track-metadata-module="primary nav" track-metadata-position="nav - gemini api" track-name="gemini api" track-type="nav" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[1]/a">
    Gemini API
  
    </a>
</tab>
<tab class="devsite-overflow-tab" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]"><!-- -->
<a aria-label="Extended Navigation" class="devsite-icon devsite-icon-arrow-drop-down" href="#" style="border: 2px solid red;" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/a"><!--?lit$8296333005$-->More</a>
<div class="devsite-tabs-overflow-menu" scrollbars="" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/div">
<tab xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/div/tab[1]">
<a class="devsite-tabs-content gc-analytics-event" data-category="Site-Wide Custom Events" data-label="Tab: Gemma" href="https://ai.google.dev/gemma" track-metadata-eventdetail="https://ai.google.dev/gemma" track-metadata-module="primary nav" track-metadata-position="nav - gemma" track-name="gemma" track-type="nav" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/div/tab[1]/a">
    Gemma
  
    </a>
</tab><tab xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/div/tab[2]">
<a class="devsite-tabs-content gc-analytics-event" data-category="Site-Wide Custom Events" data-label="Tab: Google AI Edge" href="https://ai.google.dev/edge" track-metadata-eventdetail="https://ai.google.dev/edge" track-metadata-module="primary nav" track-metadata-position="nav - google ai edge" track-name="google ai edge" track-type="nav" xpath="/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/div/tab[2]/a">
    Google AI Edge
  

Query: Click on "Gemma" under the "More" dropdown menu.
Completion:
```python
# Let's think step by step

# First, we notice that the query asks us to click on the "Gemma" option under the "More" dropdown menu.

# In the provided HTML, we see that the "More" dropdown menu is within a tab element with a specific class and role attribute.

# The "More" dropdown menu can be identified by its class 'devsite-overflow-tab' and contains a link element with the text 'More'.

# We need to interact with this dropdown menu to reveal the hidden options.

# Specifically, for the "More" dropdown menu, there is an anchor element within a tab element:
# /html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/a

# We can use this XPATH to identify and click on the "More" dropdown menu:
more_dropdown = driver.find_element(By.XPATH, "/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/a")
more_dropdown.click()

# After clicking the "More" dropdown, we need to select the "Gemma" option from the revealed menu.

# The "Gemma" option is located within the dropdown menu and can be identified by its anchor element with the corresponding text:
# /html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/div/tab[1]/a

# Thus, we use this XPATH to identify and click on the "Gemma" option:
gemma_option = driver.find_element(By.XPATH, "/html/body/section/devsite-header/div/div[1]/div/div/div[2]/div[1]/devsite-tabs/nav/tab[2]/div/tab[1]/a")
gemma_option.click()
```
---
"""
