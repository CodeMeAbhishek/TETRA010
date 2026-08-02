import json
import os

def build_kdigo_grid():
    # As per the KDIGO heatmap images (kdigo_heatmap (1).png and kdigo_heatmap (2).png)
    # G1: >90, G2: 60-89, G3a: 45-59, G3b: 30-44, G4: 15-29, G5: <15
    # A1: <30, A2: 30-300, A3: >300
    
    grid = {
        "G1": {"A1": "Green", "A2": "Yellow", "A3": "Orange"},
        "G2": {"A1": "Green", "A2": "Yellow", "A3": "Orange"},
        "G3a": {"A1": "Yellow", "A2": "Orange", "A3": "Red"},
        "G3b": {"A1": "Orange", "A2": "Red", "A3": "Red"},
        "G4": {"A1": "Orange", "A2": "Red", "A3": "Red"},
        "G5": {"A1": "Red", "A2": "Red", "A3": "Red"}
    }
    
    output_path = os.path.join(os.path.dirname(__file__), "kdigo_ckd_grid.json")
    with open(output_path, "w") as f:
        json.dump(grid, f, indent=4)
        
    print("KDIGO CKD grid generated at:", output_path)

if __name__ == "__main__":
    build_kdigo_grid()
