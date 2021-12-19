import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import re
from tqdm.notebook import tqdm, trange
from IPython.display import clear_output

import numpy as np

class TAScrapper():
    restaurants_data = {}
    def __init__(self, city, show=False):
        self.PATH = 'chromedriver.exe'
        self.options = Options()
        if not show:
            self.options.add_argument("--headless")
        self.city = city
        # List for storing links to restaurants data
        self.restaurants_hrefs = []
        # Dict for storing dicts with restaurants information
        self.restaurants_data = []
    
    
    def _verbose(message):
        def decorator(func):
            def wrapper(*args, **kwargs):
                print(message)
                clear_output(wait=True)
                return func(*args, **kwargs) 
            return wrapper
        return decorator


    @_verbose(message = 'starting driver...')
    def start_driver(self):
        self.driver = webdriver.Chrome(options=self.options)
        self.driver.set_window_size(600, 800)
        
        
    @_verbose(message = 'opening TripAdvisor...')
    def open_tripadvisor(self):
        self.driver.get('https://www.tripadvisor.com/')
        
        
    @_verbose(message = 'accepting cookies...')
    def accept_cookies(self):
        # id
        
        WebDriverWait(self.driver, timeout=10).until(lambda d: d.find_element_by_id('onetrust-accept-btn-handler'))
        self.driver.find_element_by_id('onetrust-accept-btn-handler').click()
        
        
    @_verbose(message = 'searching the city...')
    def search_the_city(self, city):
        WebDriverWait(self.driver, timeout=3).until(lambda d: d.find_element_by_class_name('_3qLQ-U8m'))
        inputElement = self.driver.find_element_by_class_name('_3qLQ-U8m')
        inputElement.send_keys(city)
        time.sleep(0.5)
        WebDriverWait(self.driver, timeout=10).until(lambda d: d.find_element_by_class_name("_1c2ocG0l"))
        self.driver.find_element_by_class_name("_1c2ocG0l").click()
    
    
    @_verbose(message = 'choosing the list of restaurants category...')
    def filter_restaurants(self):
        attempts = 0
        while True:
            try:
                WebDriverWait(self.driver, timeout=10).until(lambda d: d.find_element_by_class_name("_2HtGEjYV"))
                filters = self.driver.find_elements_by_class_name("_2HtGEjYV")
                index = [ind for ind, filt in enumerate(filters[:-1]) if re.findall('(?<=m\/)(\w+)', filt.get_attribute('href')) == ['Restaurants']][0]
                filters[index].click()
                break
            except:
                    if attempts !=10:
                        WebDriverWait(self.driver, timeout=10).until(lambda d: d.find_element_by_css_selector("[aria-label='Next']"))
                        time.sleep(3)
                        self.driver.find_element_by_css_selector("[aria-label='Next']").click()
                    else:
                        raise RuntimeError('Cannot filter restaurants, FATAL')
                        break
                
                
    @_verbose(message = 'turning off filters...')                                              
    def clear_filters(self):
        try:
            WebDriverWait(self.driver, timeout=10).until(lambda d: d.find_element_by_class_name('_3bGkSG3Z'))
            self.driver.find_element_by_class_name('_3bGkSG3Z').click()
        except:
            pass
    
    
    @_verbose(message = 'getting links to the restaurants pages...')
    def get_restaurants_hrefs(self):
        WebDriverWait(self.driver, timeout=10, ).until(lambda d: d.find_element_by_class_name('_15_ydu6b'))
        return [elem.get_attribute('href') for elem in self.driver.find_elements_by_class_name('_15_ydu6b')]
    
    
    @_verbose(message = 'going to the next page...')
    def next_page(self):
        self.driver.find_elements_by_class_name('next')[0].click()
        time.sleep(3)
                       
            
    @_verbose(message = 'collecting hrefs from restaurant lists...')
    def collect_hrefs(self, n_pages):
        if n_pages == 'all':
            n_pages = 9999
        n = 0
        pages=0
        while pages!=n_pages:
            while n!=40: # if links loaded
                time.sleep(1)
                hrefs_from_page = self.get_restaurants_hrefs()
                if len(hrefs_from_page)!=0:
                    
                    break
                else:
                    n+=1
            self.restaurants_hrefs = self.restaurants_hrefs + hrefs_from_page
            try:
                self.next_page()
                pages +=1
                print (f'collected {len(self.restaurants_hrefs)} links from {pages} pages')
                clear_output(wait=True)
            except:
                break
        
    
    @_verbose(message = 'collecting restaurant name...')
    def collect_name(self, rest_data):
        # Make few attempts to be sure that page loaded correctly (sometimes buggs appears on website)
        attempts = 0
        while True:
            try:
                WebDriverWait(self.driver, timeout=10).until(lambda d: self.driver.find_element_by_class_name('_3a1XQ88S'))
                rest_data['Name'] = self.driver.find_element_by_class_name('_3a1XQ88S').text # Name
                break
            except:
                if attempts !=2:
                    self.driver.refresh()
                    attempts +=1
                else:
                    rest_data['Name'] = None
                    break
                    
    
    @_verbose(message = 'collecting restaurant reviews count...')
    def collect_reviews_count(self, rest_data):
        # Collecting data
        try:
            WebDriverWait(self.driver, timeout=2).until(lambda d: self.driver.find_element_by_class_name('_3Wub8auF'))
            rest_data['N_reviews'] = re.findall('\d+', self.driver.find_element_by_class_name('_3Wub8auF').text)[0]
        except:
            rest_data['N_reviews'] = None   
        # Turning off review filters
        try:
            if len(self.driver.find_elements_by_class_name('ui_tag_box')) > 1:
                [i for i in self.driver.find_elements_by_class_name('ui_tag_box') if i.get_attribute('data-tracker') == 'English'][0].click()
                time.sleep(1)
        except: 
            pass
        rest_data['Review_ratings'] = {}
        # Collecting data
        rev_names = ['Excellent', 'Very good', 'Average', 'Poor', 'Terrible'] # Reviews marks
        try:
            WebDriverWait(self.driver, timeout=2).until(lambda d: self.driver.find_element_by_class_name('row_num '))
            rev_vals = [el.text for el in self.driver.find_elements_by_class_name('row_num ') if len(el.text)>0] # Reviews count
        except:
            rev_vals = [None]*5
        # Filling dictionary
        for k, v in zip(rev_names, rev_vals):
            rest_data['Review_ratings'][k] = v 

            
    @_verbose(message = 'collecting restaurant location data...')
    def collect_location_data(self, rest_data):
        try:
            WebDriverWait(self.driver, timeout=2).until(lambda d: self.driver.find_elements_by_class_name('rAA8XwlX'))
            rest_data['Latitude'], rest_data['Longitude'] = re.findall('\d+.\d+,\d+.\d+', self.driver.find_elements_by_class_name('rAA8XwlX')[0].get_attribute('src'))[0].split(',')
        except:
            rest_data['Latitude'], rest_data['Longitude'] = (None, None)
        try:
            rest_data['Adres'] = self.driver.find_element_by_class_name('_2saB_OSe').text
        except:
            rest_data['Adres'] = None
        try:
            rest_data['District'] = self.driver.find_element_by_class_name('_1OBMr94N').text
        except: 
            rest_data['District'] = None
            
    
    @_verbose(message = 'collecting restaurant working hours...')
    def collect_working_hours_data(self, rest_data):
        rest_data['Open_hours'] = {}
        rest_data['Close_hours'] = {}
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        try:
            # Open working time table
            WebDriverWait(self.driver, timeout=2).until(lambda d: self.driver.find_element_by_class_name('_1h0LGVD2'))
            self.driver.find_element_by_class_name('_1h0LGVD2').click()
            # Collecting data
            
            working_days, working_hours = (np.array([i.text.split('\n') for i in self.driver.find_elements_by_class_name('_2UEvprRr')])).T.tolist()
            # Filling dictionary
            for i in days:
                if i in working_days:
                    opened, closed = working_hours[working_days.index(i)].split(' - ')
                    rest_data['Open_hours'][i] = opened
                    rest_data['Close_hours'][i] = closed
                else:
                    rest_data['Open_hours'][i] = 'Closed'
                    rest_data['Close_hours'][i] = 'Closed'
            # Close working time table
            self.driver.find_element_by_class_name('_1h0LGVD2').click()
        except:
            for i in days:
                rest_data['Open_hours'][i] = None
                rest_data['Close_hours'][i] = None
    
    
    @_verbose(message = 'collecting restaurant details...')
    def collect_details(self, rest_data):
        # Open all the details
        try:
            WebDriverWait(self.driver, timeout=2).until(lambda d: self.driver.find_element_by_class_name('_3xJIW2mF'))
            self.driver.find_element_by_class_name('_3xJIW2mF').click()
        except: 
            pass
        rest_data['Details'] = {}
        details_titles = ['Price_range', 'Cuisines', 'Special_diets', 'About', 'Meals', 'Features']
        # Setting all details to None
        for k in details_titles:
            rest_data['Details'][k] = None
        try:
            keys = [i.text for i in self.driver.find_elements_by_class_name('_14zKtJkz')] # Collected details names
            keys = [i[0]+str.lower(i[1:].replace(' ', '_')) for i in keys]
            values = [i.text for i in self.driver.find_elements_by_class_name('_1XLfiSsv')] # Collected details info
            for k, v in zip(keys, values):
                rest_data['Details'][k] = v
        except:
            pass
        
    
    def get_hrefs(self, n_pages):
        self.start_driver()
        self.open_tripadvisor()
        self.accept_cookies()
        self.search_the_city(self.city)
        self.filter_restaurants()
        time.sleep(1)
        self.clear_filters()
        self.collect_hrefs(n_pages)
        self.driver.close()
        clear_output()
        print ('Done')
        
        
    def get_restaurants_data(self):
        self.start_driver()
        assert len(self.restaurants_hrefs) !=0, "Can't find links to restaurants pages. Try get_hrefs(city, n_pages) before."
        for num, rest_href in enumerate(self.restaurants_hrefs):
            
            self.driver.execute_script(f"window.open('{rest_href}');")
            time.sleep(1)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            
            rest_data = {}
            self.collect_name(rest_data)
            self.collect_reviews_count(rest_data)
            self.collect_location_data(rest_data)
            self.collect_working_hours_data(rest_data)
            self.collect_details(rest_data)
        
            print (f'Scrapped {num} from {len(self.restaurants_hrefs)} restauratns pages')
            clear_output(wait=True)
            self.restaurants_data.append(rest_data)
            self.driver.close()
            # switching to window with list of restaurants
            self.driver.switch_to.window(self.driver.window_handles[0])
        self.driver.close()
        clear_output()
        print ('Done')
        
        
    @_verbose('saving restaurants data...')        
    def save_collected_data(self, folder=""):
        with open(f'{folder}restaurants_data_{self.city}.json', 'w') as outfile:
            json.dump(self.restaurants_data, outfile)
        clear_output()
        print ('Done')
            
            
    @_verbose('saving restaurants links...')        
    def save_collected_hrefs(self, folder=""):
        with open(f'{folder}restaurants_hrefs_{self.city}.json', 'w') as outfile:
            json.dump(self.restaurants_hrefs, outfile)
        clear_output()
        print ('Done')
    
    
    @_verbose('loading restaurants hrefs...')
    def load_collected_hrefs(self, folder=""):
        with open(f'{folder}restaurants_hrefs_{self.city}.json') as inputfile:
            self.restaurants_hrefs = json.load(inputfile)
        clear_output()
        print ('Done')
    
    
    @_verbose('loading restaurants data...')
    def load_collected_data(self, folder=""):
        with open(f'{folder}restaurants_data_{self.city}.json') as inputfile:
            self.restaurants_data = json.load(inputfile)
        clear_output()
        print ('Done')