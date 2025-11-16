#!/usr/bin/env python3
import re
from bs4 import BeautifulSoup
import sys
import os
import json 

# --- IMPORTANT: Set the target file path directly for this run ---
TARGET_HTML_FILE = 'gphotos_dump_1763267163.html'
# ------------------------------------------------------------------

def _load_name_data():
    """Load names and special cases from names.json for simulation."""
    names_file = 'names.json' # Assumes names.json is in the same directory
    if not os.path.exists(names_file):
        print(f"[SIMULATION] Warning: '{names_file}' not found. Cannot run name processing simulation.")
        return [], {}

    try:
        with open(names_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            names_list = data.get('names', [])
            special_cases = data.get('special_cases', {})
            
            # Extract clean names (used for reference, not mandatory for filtering in the original snippet)
            clean_names = []
            for name_entry in names_list:
                clean = ''.join(c for c in name_entry if c not in '()').strip()
                if clean and clean != '4':
                    clean_names.append(clean)
            
            return clean_names, special_cases
            
    except Exception as e:
        print(f"[SIMULATION] Error loading {names_file}: {e}")
        return [], {}

def find_textarea_div_info(file_path):
    """
    Parses HTML content from the given file path to find all <textarea> elements 
    and reports information about their immediate parent <div> containers.
    This also provides the value corresponding to BrowserController._last_description 
    (from the first textarea found) for the name injection simulation.
    """
    try:
        # Read the entire file content from the specified path
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        print("Please ensure the file path is correct.")
        return [], None, '(EMPTY)', None
    except Exception as e:
        print(f"Error reading file: {e}")
        return [], None, '(EMPTY)', None

    # Initialize BeautifulSoup parser
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all <textarea> elements in the document
    textareas = soup.find_all('textarea')

    # List to store the relevant info for summary/return
    div_info_list = []
    # current_desc must be taken from the first textarea for simulation purposes
    current_desc = '(EMPTY)'
    target_textarea = None # Initialize target_textarea
    
    if not textareas:
        print(f"No <textarea> elements were found in '{file_path}'.")
        return [], soup, current_desc, None

    print(f"--- Found {len(textareas)} <textarea> elements in '{file_path}' ---")

    # The target textarea (for description) is always the first one found
    target_textarea = textareas[0]
    current_desc = (target_textarea.string or '').strip()
    
    for i, textarea in enumerate(textareas):
        # 1. Get Textarea info (ID and Name are useful for targeting)
        textarea_id = textarea.get('id', 'N/A')
        textarea_name = textarea.get('name', 'N/A')
        textarea_value = textarea.string or '(EMPTY)'
        
        info_item = {
            'index': i + 1,
            'textarea_id': textarea_id,
            'textarea_name': textarea_name,
            'value': textarea_value.strip(),
            'div_id': 'N/A',
            'div_class': 'N/A',
            'ancestor_path': 'N/A'
        }

        print(f"\nTextarea {i + 1} Details:")
        if i == 0:
             print(f"  (This is the target description field: BrowserController._last_description)")
        
        print(f"  ID:         {info_item['textarea_id']}")
        print(f"  Name:       {info_item['textarea_name']}")
        print(f"  Value:      '{info_item['value'][:60]}{'...' if len(info_item['value']) > 60 else ''}'")

        # Find the parent info
        parent_tag = textarea.find_parent('div')

        if parent_tag:
            div_id = parent_tag.get('id', 'N/A')
            div_class_list = parent_tag.get('class', ['N/A'])
            div_class = div_class_list[0] if div_class_list else 'N/A'
            
            info_item['div_id'] = div_id
            info_item['div_class'] = div_class

            print(f"  Parent Tag: {parent_tag.name.upper()} (closest DIV ancestor)")
            print(f"  Parent ID:  {div_id}")
            print(f"  Parent Class: {div_class}")

            path = []
            element = parent_tag
            while element and element.name not in ['html', 'body']:
                identifier = f"#{element.get('id')}" if element.get('id') else f".{element.get('class')[0]}" if element.get('class') else ""
                path.append(f"{element.name.upper()}{identifier}")
                element = element.parent
            path.reverse()
            
            # Show path from root to the immediate parent
            path_display = ' > '.join(path)
            info_item['ancestor_path'] = path_display

            print(f"  > Ancestor Path: {path_display}")
        
        div_info_list.append(info_item)
    
    # Print the final summary of the target divs (consolidated view)
    if div_info_list:
        print("\n" + "="*50)
        print("SUMMARY: TEXTAREA INFORMATION")
        print("="*50)
        for item in div_info_list:
            print(f"Textarea {item['index']} (Name: {item['textarea_name']}):")
            print(f"  Parent Div ID:    {item['div_id']}")
            print(f"  Parent Div Class: {item['div_class']}")
            print(f"  Value Preview:    '{item['value'][:40]}{'...' if len(item['value']) > 40 else ''}'")
        print("="*50)

    # Note: current_desc is the value of the *first* textarea, used for simulation
    # Also return the target_textarea element to help find the correct ancestor
    return div_info_list, soup, current_desc, target_textarea


def _find_closest_sidebar_root(target_element):
    """
    Finds the closest parent element that likely represents the root of the active 
    details sidebar (to scope the search for album names). 
    We look for the 'DIV.ZPTMcc' which usually contains the photo details.
    """
    if not target_element:
        return None
        
    # Traverse up to find the closest ancestor with class 'ZPTMcc'
    sidebar_root = target_element.find_parent('div', class_='ZPTMcc')
    
    if sidebar_root:
        return sidebar_root
    
    # Fallback to the parent that holds the description input, if ZPTMcc is missed
    return target_element.find_parent('div', class_='YW656b')


def is_element_visually_hidden(element):
    """
    Checks for common attributes or styles that indicate an element is hidden
    in the context of a Google Photos sidebar, using BeautifulSoup.
    
    NOTE: This is a heuristic check, as BeautifulSoup cannot run CSS layout.
    """
    current = element
    while current and current.name != 'body':
        # 1. Check for aria-hidden="true" (Strong indicator for non-visual elements)
        if current.get('aria-hidden') == 'true':
            return True
        # 2. Check for inline style display: none
        style = current.get('style', '')
        if 'display: none' in style.lower():
            return True
        current = current.parent
    return False

def find_injected_name_candidates(soup, target_textarea):
    """
    Extracts elements targeted by the _extract_and_add_names function
    for name injection and returns the list of candidates, applying a 
    visibility filter.
    """
    print("\n" + "@"*50)
    print("INJECTED NAME CANDIDATES (Targeted by _extract_and_add_names)")
    print("@"*50)
    
    # Find the root of the *active* sidebar panel using the description field as a starting point
    sidebar_root = _find_closest_sidebar_root(target_textarea)

    if not sidebar_root:
        print("ERROR: Could not find the active sidebar root (ZPTMcc or YW656b). Aborting search.")
        return []

    # Safety check for class existence before printing
    sidebar_class = sidebar_root.get('class')[0] if sidebar_root.get('class') else 'N/A'
    print(f"Scoped search to active sidebar root: <div class='{sidebar_class}...'>")

    found_candidates = []

    # === NEW: Global Album Search (like SUM does) ===
    all_dgvy7_divs_global = soup.find_all('div', class_='DgVY7')
    album_candidates = []

    print(f"\n=== ALL ALBUMS FOUND IN DOCUMENT (div.DgVY7 > div.AJM7gb): {len(all_dgvy7_divs_global)} ===")
    if all_dgvy7_divs_global:
        for i, dgvy7_div in enumerate(all_dgvy7_divs_global):
            name_div = dgvy7_div.find('div', class_='AJM7gb')
            if name_div and name_div.text:
                text = name_div.text.strip()
                is_hidden = is_element_visually_hidden(name_div)
                in_sidebar = sidebar_root and sidebar_root in [p for p in dgvy7_div.parents]

                status_tag = "(VISIBLE/PROCESSED)" if not is_hidden else "(HIDDEN/IGNORED)"
                location = "*** IN SIDEBAR ***" if in_sidebar else "outside sidebar"

                print(f"  {i+1}. '{text}' ({status_tag}, {location})")

                # Add visible, non-year-prefixed albums to candidates
                if not is_hidden and not (len(text) >= 4 and text[0:4].isdigit()):
                    album_candidates.append(text)

        print(f"\nAlbum candidates passed to processing (visible, non-year-prefixed): {album_candidates if album_candidates else '[]'}")
        found_candidates.extend(album_candidates)
    else:
        print("  (none found)")

    # === Albums in sidebar (old approach - for comparison) ===
    all_dgvy7_divs_sidebar = sidebar_root.find_all('div', class_='DgVY7') if sidebar_root else []
    if all_dgvy7_divs_sidebar:
        print(f"\n[COMPARISON] Albums in sidebar (old scoped search): {len(all_dgvy7_divs_sidebar)}")
        for i, dgvy7_div in enumerate(all_dgvy7_divs_sidebar):
            name_div = dgvy7_div.find('div', class_='AJM7gb')
            if name_div and name_div.text:
                is_hidden = is_element_visually_hidden(name_div)
                status = "(HIDDEN/IGNORED)" if is_hidden else "(VISIBLE)"
                print(f"  {i+1}. '{name_div.text.strip()}' {status}")

    # === Face/People Tags (existing code, enhanced) ===
    all_y8x4pc_spans_global = soup.find_all('span', class_='Y8X4Pc')
    span_candidates = []

    print(f"\n=== ALL FACES FOUND IN DOCUMENT (span.Y8X4Pc): {len(all_y8x4pc_spans_global)} ===")
    if all_y8x4pc_spans_global:
        for i, span in enumerate(all_y8x4pc_spans_global):
            text = span.text.strip()

            if text:
                is_hidden = is_element_visually_hidden(span)
                in_sidebar = sidebar_root and sidebar_root in [p for p in span.parents]

                status_tag = "(VISIBLE/PROCESSED)" if not is_hidden else "(HIDDEN/IGNORED)"
                location = "*** IN SIDEBAR ***" if in_sidebar else "outside sidebar"

                print(f"  {i+1}. '{text}' ({status_tag}, {location})")

                if not is_hidden:
                    span_candidates.append(text)

        print(f"\nFace candidates passed to processing (visible): {span_candidates if span_candidates else '[]'}")
        found_candidates.extend(span_candidates)
    else:
        print("  (none found)")

    # === Faces in sidebar (old approach - for comparison) ===
    all_y8x4pc_spans_sidebar = sidebar_root.find_all('span', class_='Y8X4Pc') if sidebar_root else []
    if all_y8x4pc_spans_sidebar:
        spans_to_check = all_y8x4pc_spans_sidebar[-5:]
        print(f"\n[COMPARISON] Faces in sidebar last 5 (old scoped search): {len(spans_to_check)}")
        for i, span in enumerate(spans_to_check):
            text = span.text.strip()
            if text:
                is_hidden = is_element_visually_hidden(span)
                status = "(HIDDEN/IGNORED)" if is_hidden else "(VISIBLE)"
                print(f"  {i+1}. '{text}' {status}")

    print(f"\n{'='*50}")
    print(f"TOTAL CANDIDATES TO PROCESS: {len(found_candidates)}")
    print(f"Candidates: {found_candidates}")
    print("@"*50)
    return found_candidates


def analyze_textareas(soup, sidebar_root):
    """
    NEW FUNCTION: Analyze all textareas like SUM does.
    """
    print("\n" + "="*50)
    print("TEXTAREA ANALYSIS")
    print("="*50)

    all_textareas = soup.find_all('textarea', attrs={'aria-label': 'Description'})

    print(f"\n=== ALL TEXTAREAS FOUND IN DOCUMENT: {len(all_textareas)} ===")

    if not all_textareas:
        print("  (none found)")
        return

    for i, ta in enumerate(all_textareas):
        textarea_id = ta.get('id', '(no id)')
        textarea_class = ' '.join(ta.get('class', [])) if ta.get('class') else '(no class)'
        value = (ta.string or '')

        # Normalize whitespace similar to browser behavior
        value_norm = ' '.join(value.split()).strip()

        is_hidden = is_element_visually_hidden(ta)
        in_sidebar = sidebar_root and sidebar_root in [p for p in ta.parents]

        status = 'HIDDEN' if is_hidden else 'VISIBLE'
        location = '*** IN SIDEBAR ***' if in_sidebar else 'outside sidebar'
        content_status = f"has content ({len(value_norm)} chars)" if value_norm else "empty"

        print(f"\n  {i+1}. textarea (aria-label='Description', {content_status})")
        print(f"      ID: {textarea_id}")
        print(f"      Class: {textarea_class}")
        print(f"      Location: {location}")
        print(f"      Visibility: {status}")
        if value_norm:
            preview = value_norm[:50]
            print(f"      Content preview: '{preview}...'")

    print("\n" + "="*50)


def simulate_name_processing(candidates, current_desc):
    """
    Simulates the filtering and processing logic of _extract_and_add_names.
    """
    print("\n" + "*"*50)
    print("SIMULATION OF NAME APPENDING LOGIC")
    print("*"*50)
    
    clean_names, special_cases = _load_name_data()
    
    if not candidates:
        print("No candidates found to process.")
        return

    # Normalize the current description for comparison
    current_desc = current_desc.strip()
    desc_normalized = ' '.join(current_desc.split()).lower()
    
    names_to_append = []
    
    if desc_normalized == '(empty)':
        desc_normalized = ''

    # We must iterate over the full list of candidates found, as the filtering 
    # logic depends on the order of iteration.
    for original_name in candidates:
        print(f"\n[PROCESS] Checking candidate: '{original_name}'")
        
        name_to_check = ' '.join(original_name.split())
        
        # 1. Year/Digit Prefix Check (e.g., skips '2022...')
        if name_to_check and name_to_check[0:4].isdigit():
            print(f"[SKIP] '{original_name}' -> Skipped (Starts with year/digit prefix)")
            continue
            
        if name_to_check and name_to_check.startswith("0"):
            print(f"[SKIP] '{original_name}' -> Skipped (Starts with '0')")
            continue

        # 2. Special Case Mapping
        mapped_name = special_cases.get(name_to_check, name_to_check)
        
        if mapped_name != name_to_check:
            print(f"[MAP] '{original_name}' -> Mapped to '{mapped_name}'")
        
        # 3. Duplication Check
        # Normalize the name being checked for better comparison
        normalized_name_check = ' '.join(mapped_name.split()).lower()
        
        # The duplication check in the original script is simply 'found_name in desc_normalized'
        if normalized_name_check in desc_normalized or normalized_name_check in [n.lower() for n in names_to_append]:
            print(f"[SKIP] '{original_name}' -> Skipped (Already in description or list of names to be added)")
            continue
            
        # 4. Success - Name is prepared for addition
        names_to_append.append(mapped_name)
        print(f"[ADD] '{original_name}' -> ADDED as '{mapped_name}'")

        # Update the normalized description *for the next iteration's check*
        # This simulates the script's behavior of checking against the growing description
        desc_normalized += ' ' + normalized_name_check


    print("\n" + "-"*50)
    if names_to_append:
        print(f"Final Names That Would Be Appended: {names_to_append}")
        print(f"Total appended: {len(names_to_append)}")
    else:
        print("No names passed all filtering checks to be appended.")
    print("*"*50)

    
def find_other_contextual_info(soup):
    """
    Extracts high-level contextual information from the parsed HTML,
    corresponding to data points used by BrowserController and AssistantUI.
    """
    print("\n" + "#"*50)
    print("CONTEXTUAL INFORMATION (BrowserController & AssistantUI Data)")
    print("#"*50)
    
    # 1. Page Title (Often used as photo metadata/name)
    title = soup.find('title')
    page_title = title.string.strip() if title else 'N/A'
    print(f"Page Title (Metadata): {page_title}")

    # 2. Canonical URL (Corresponds to BrowserController._last_url)
    # Google Photos often uses <base href> and <link rel="canonical">
    base_tag = soup.find('base')
    base_href = base_tag.get('href') if base_tag else 'N/A'
    
    canonical_link = soup.find('link', rel='canonical')
    canonical_href = canonical_link.get('href') if canonical_link else 'N/A'
    
    # The full URL is often base_href + canonical_href or simply the canonical_href
    full_url = canonical_href if canonical_href != 'N/A' else base_href
    print(f"Full Photo URL (BrowserController._last_url): {full_url}")

    # 3. Short URL Preview (Corresponds to UI_COMPONENTS display logic)
    if full_url != 'N/A':
        # The UI uses url.split('/')[-1] to shorten the URL for display
        short_url = full_url.split('/')[-1]
        print(f"  > UI Preview Short URL: {short_url}")
    else:
        print("  > UI Preview Short URL: N/A")
        
    print("#"*50)
    

def main():
    """
    Main execution function to run the analysis.
    """
    # 1. Check for the BeautifulSoup dependency first
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("Error: The 'beautifulsoup4' library is not installed.")
        print("You must install it using: pip install beautifulsoup4")
        sys.exit(1)
    # 2. Get HTML file path from command line argument or use default
    if len(sys.argv) > 1:
        html_file_path = sys.argv[1]
    else:
        # Fallback to TARGET_HTML_FILE if it exists (for dump-explorer.py compatibility)
        try:
            html_file_path = TARGET_HTML_FILE
        except NameError:
            print("Error: No HTML file specified.")
            print("Usage: python3 da.py <html_file>")
            sys.exit(1)

    # Check if the file exists
    if not os.path.exists(html_file_path):
        print(f"Error: The target file '{html_file_path}' does not exist.")
        sys.exit(1)
        
    # 3. Run the main analysis functions
    
    # Find Textarea Info and Current Description
    div_info_list, soup, current_desc, target_textarea = find_textarea_div_info(html_file_path)
    
    if soup:
        # NEW: Analyze textareas
        sidebar_root = _find_closest_sidebar_root(target_textarea)
        analyze_textareas(soup, sidebar_root)
        
        # Find Injected Name Candidates
        candidates = find_injected_name_candidates(soup, target_textarea)
        
        # Simulate Processing Logic
        simulate_name_processing(candidates, current_desc)
        
        # Find Other Contextual Info 
        find_other_contextual_info(soup)


if __name__ == '__main__':
    main()
