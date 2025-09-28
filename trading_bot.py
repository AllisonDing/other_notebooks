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
        self.max_price = 23.0  # Set to $30 to cover $22.99 plus any small price variations
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
            print("✓ Browser launched successfully")
        except Exception as e:
            print(f"Error creating driver: {e}")
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise
    
    def monitor_for_availability(self):
        """Monitor the Labubu PIN for Love product for availability"""
        print(f"\nMonitoring POP MART Labubu Monster PIN for Love")
        print(f"Target price: $22.99 (max: ${self.max_price})")
        print(f"Product: {self.product_url}")
        print(f"Checking every {self.check_interval} second(s)")
        print(f"Max attempts: {self.max_attempts}\n")
        
        for attempt in range(self.max_attempts):
            if attempt % 10 == 0:  # Print every 10th attempt to reduce console spam
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
                
                # Check availability
                try:
                    # Look for add to cart button
                    add_to_cart = self.driver.find_element(By.ID, "add-to-cart-button")
                    if add_to_cart.is_enabled():
                        print("\nPRODUCT IS AVAILABLE!")
                        
                        # Check price
                        try:
                            price_element = self.driver.find_element(By.CSS_SELECTOR, ".a-price-whole")
                            price = float(price_element.text.replace(',', ''))
                            
                            if price <= self.max_price:
                                print(f"✓ Price ${price} is acceptable (within ${self.max_price} limit)")
                                add_to_cart.click()
                                print("SUCCESSFULLY ADDED TO CART!")
                                
                                # Optional: Proceed to checkout
                                try:
                                    time.sleep(1)
                                    proceed_to_checkout = self.driver.find_element(By.NAME, "proceedToRetailCheckout")
                                    proceed_to_checkout.click()
                                    print("Proceeding to checkout!")
                                except:
                                    print("! Could not auto-proceed to checkout - please complete manually")
                                
                                return True
                            else:
                                print(f"✗ Price ${price} exceeds threshold ${self.max_price}")
                        except:
                            print("! Could not determine price, attempting to add anyway")
                            add_to_cart.click()
                            print("Added to cart (price unknown)")
                            return True
                            
                except NoSuchElementException:
                    if attempt % 50 == 0:  # Print status every 50 attempts
                        print("  ... Still checking, product not available yet")
                
                # Wait before next check
                if attempt < self.max_attempts - 1:
                    time.sleep(self.check_interval)
                    
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    print("\nRATE LIMITED! Waiting 30 seconds...")
                    time.sleep(30)
                else:
                    if attempt % 10 == 0:  # Only print errors occasionally
                        print(f"Error: {e}")
                    time.sleep(self.check_interval)
        
        print("\nMonitoring complete - product did not become available")
        return False
    
    def close_browser(self):
        """Close the browser and exit"""
        if self.driver:
            self.driver.quit()
            print("Browser closed")
    
    def run(self):
        """Main execution method"""
        try:
            self.launch_browser()
            self.monitor_for_availability()
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            self.close_browser()

# Main execution
if __name__ == "__main__":
    monitor = LabubuMonitor()
    monitor.run()