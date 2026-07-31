import json
import os

def generate_structure():
    data = {
        "lab_based": {},
        "non_lab_based": {}
    }
    
    # Lab based axes
    diabetes = ["diabetes_yes", "diabetes_no"]
    sex = ["male", "female"]
    smoking = ["smoker", "non_smoker"]
    age_bands = ["40-49", "50-59", "60-69", "70+"]
    sbp_bands = ["120-139", "140-159", "160-179", "180+"]
    chol_bands = ["4", "5", "6", "7", "8"]
    
    # Non-lab based axes
    bmi_bands = ["<20", "20-24", "25-29", "30+"]
    
    for d in diabetes:
        data["lab_based"][d] = {}
        data["non_lab_based"][d] = {}
        for s in sex:
            data["lab_based"][d][s] = {}
            data["non_lab_based"][d][s] = {}
            for sm in smoking:
                data["lab_based"][d][s][sm] = {}
                data["non_lab_based"][d][s][sm] = {}
                for a in age_bands:
                    data["lab_based"][d][s][sm][a] = {}
                    data["non_lab_based"][d][s][sm][a] = {}
                    for sbp in sbp_bands:
                        data["lab_based"][d][s][sm][a][sbp] = {}
                        data["non_lab_based"][d][s][sm][a][sbp] = {}
                        
                        # Lab based: cholesterol
                        for c in chol_bands:
                            data["lab_based"][d][s][sm][a][sbp][c] = "<5%" # default placeholder
                            
                        # Non-lab based: BMI
                        for b in bmi_bands:
                            data["non_lab_based"][d][s][sm][a][sbp][b] = "<5%" # default placeholder
                            
    with open("c:\\NUV\\tetrathon\\who_cvd_charts.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    generate_structure()
    print("who_cvd_charts.json generated.")
