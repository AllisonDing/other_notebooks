from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
import tempfile
import subprocess

class LabubuMonitor:
    def __init__(self):
        self.driver = None
        self.actions = None
        self.wait = None
        
        # Product monitoring parameters
        self.product_url = "https://www.amazon.com/POP-MART-Monster-PIN-Love/dp/B0FJFV4PQN"
        self.buy_whole_set = True  # Set to True to buy whole set, False for single box
        self.max_price_single = 23.0  # Max price for single box ($22.99)
        self.max_price_whole_set = 322.0  # Max price for whole set ($321.86)
        self.check_interval = 1  # Seconds between checks for aggressive mode
        self.max_attempts = 3600  # Check for 1 hour max
    
    def launch_browser(self):
        """Launch browser with proper Chrome configuration"""
        # Kill existing Chrome processes
        try:
            subprocess.run(["pkill", "-f", "chrome"], check=False)
            time.sleep(2)
        except:
            pass
        
        # Set up Chrome options
        chrome_options = Options()
        
        # Create unique temp directory
        temp_dir = os.path.join(tempfile.gettempdir(), f"chrome_temp_{os.getpid()}_{int(time.time())}")
        chrome_options.add_argument(f"--user-data-dir={temp_dir}")
        
        # Add necessary flags
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--no-first-run")
        chrome_options.add_argument("--no-default-browser-check")
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.actions = ActionChains(self.driver)
            self.wait = WebDriverWait(self.driver, 10)
            self.driver.maximize_window()
            print("Browser launched successfully")
        except Exception as e:
            print(f"Error creating driver: {e}")
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    
    def monitor_for_availability(self):
        """Monitor the Labubu PIN for Love product for availability"""
        option_type = "Whole Set" if self.buy_whole_set else "Single Box"
        max_price = self.max_price_whole_set if self.buy_whole_set else self.max_price_single
        expected_price = "$321.86" if self.buy_whole_set else "$22.99"
        
        print(f"\nMonitoring POP MART Labubu Monster PIN for Love - {option_type}")
        print(f"Target price: {expected_price} (max: ${max_price})")
        print(f"Product URL: {self.product_url}")
        print(f"Checking every {self.check_interval} second(s)")
        print(f"Max attempts: {self.max_attempts}\n")
        
        for attempt in range(self.max_attempts):
            if attempt % 10 == 0:  # Print every 10th attempt
                print(f"Attempt {attempt + 1}/{self.max_attempts}...")
            
            try:
                # Only reload page every 5 attempts to reduce server load
                if attempt % 5 == 0:
                    self.driver.get(self.product_url)
                    time.sleep(2)
                else:
                    # Just refresh the page
                    self.driver.refresh()
                    time.sleep(0.5)
                
                # First, select the correct option (Single Box or Whole Set)
                try:
                    # Look for the size/option selector
                    if self.buy_whole_set:
                        # Click on Whole Set option
                        whole_set_button = self.driver.find_element(
                            By.XPATH, 
                            "//button[contains(@aria-label, 'Whole Set') or contains(., 'Whole Set')]"
                        )
                        if not whole_set_button.get_attribute("aria-checked") == "true":
                            whole_set_button.click()
                            time.sleep(1)
                            print("Selected Whole Set option")
                    else:
                        # Click on Single Box option
                        single_box_button = self.driver.find_element(
                            By.XPATH, 
                            "//button[contains(@aria-label, 'Single Box') or contains(., 'Single Box')]"
                        )
                        if not single_box_button.get_attribute("aria-checked") == "true":
                            single_box_button.click()
                            time.sleep(1)
                            print("Selected Single Box option")
                except:
                    # If we can't find the option buttons, continue anyway
                    pass
                
                # Check availability
                try:
                    # Look for add to cart button
                    add_to_cart = self.driver.find_element(By.ID, "add-to-cart-button")
                    if add_to_cart.is_enabled():
                        print(f"\n{option_type} IS AVAILABLE!")
                        
                        # Check price
                        try:
                            # Try to get the price
                            price_elements = self.driver.find_elements(By.CSS_SELECTOR, ".a-price-whole, .a-price span")
                            price = 0
                            for elem in price_elements:
                                price_text = elem.text.replace(',', '').replace('$', '')
                                if price_text:
                                    try:
                                        price = float(price_text)
                                        break
                                    except:
                                        continue
                            
                            if price <= max_price:
                                print(f"Price ${price} is acceptable (within ${max_price} limit)")
                                add_to_cart.click()
                                print(f"SUCCESSFULLY ADDED {option_type} TO CART!")
                                
                                # Optional: Proceed to checkout
                                try:
                                    time.sleep(1)
                                    proceed_to_checkout = self.driver.find_element(By.NAME, "proceedToRetailCheckout")
                                    proceed_to_checkout.click()
                                    print("Proceeding to checkout!")
                                except:
                                    print("Could not auto-proceed to checkout - please complete manually")
                                
                                return True
                            else:
                                print(f"Price ${price} exceeds threshold ${max_price}")
                        except:
                            print(f"Could not determine price, attempting to add {option_type} anyway")
                            add_to_cart.click()
                            print(f"Added {option_type} to cart (price unknown)")
                            return True
                            
                except NoSuchElementException:
                    if attempt % 50 == 0:  # Print status every 50 attempts
                        print(f"Still checking, {option_type} not available yet")
                
                # Wait before next check
                if attempt < self.max_attempts - 1:
                    time.sleep(self.check_interval)
                    
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    print("\nRATE LIMITED! Waiting 30 seconds...")
                    time.sleep(30)
                else:
                    if attempt % 10 == 0:
                        print(f"Error: {e}")
                    time.sleep(self.check_interval)
        
        print(f"\nMonitoring complete - {option_type} did not become available")
        return False
    
    def close_browser(self):
        """Close the browser and exit"""
        if self.driver:
            self.driver.quit()
            print("Browser closed")
    
    def run(self):
        """Main execution method"""
        try:
            print("Starting Labubu PIN for Love Monitor...")
            if self.buy_whole_set:
                print("Mode: WHOLE SET ($321.85)")
            else:
                print("Mode: SINGLE BOX ($22.99)")
            print("-" * 50)
            
            self.launch_browser()
            self.monitor_for_availability()
            
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            self.close_browser()

# Main execution
if __name__ == "__main__":
    # Create and run the monitor
    monitor = LabubuMonitor()
    monitor.run()