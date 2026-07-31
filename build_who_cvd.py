import json

raw_lab_data = """
# Age 70-74
22 24 27 30 33  28 31 34 37 41  18 19 20 21 22  25 26 28 29 30    30 33 36 40 44  37 41 45 50 54  27 28 29 31 33  36 38 40 42 44
18 20 23 25 28  23 26 28 31 35  15 16 17 18 19  21 22 24 25 26    25 28 31 34 38  32 35 39 43 47  23 24 25 27 28  31 33 35 36 38
15 17 19 21 23  19 21 24 27 29  13 14 14 15 16  18 19 20 21 22    21 23 26 29 32  27 30 33 36 40  20 21 22 23 24  27 28 30 31 33
13 14 16 17 19  16 18 20 22 25  11 12 12 13 13  15 16 17 18 19    18 19 22 24 27  22 25 28 31 34  17 17 18 19 20  23 24 26 27 28
10 12 13 14 16  13 15 17 18 21   9 10 10 11 11  13 14 14 15 16    15 16 18 20 23  19 21 23 26 29  14 15 16 16 17  20 21 22 23 24

# Age 65-69
17 19 21 24 27  23 26 29 32 36  14 15 16 17 18  21 22 23 25 27    25 28 31 35 39  33 37 41 45 51  22 23 25 26 28  32 34 36 39 41
14 16 18 20 22  19 21 24 27 30  12 12 13 14 15  17 19 20 21 22    20 23 26 29 32  27 31 34 38 43  18 20 21 22 24  28 29 31 33 35
11 13 14 16 18  16 17 20 22 25  10 10 11 12 12  15 16 17 18 19    17 19 21 24 27  23 25 29 32 36  15 16 17 19 20  23 25 26 28 30
 9 10 12 13 15  13 14 16 18 20   8  8  9 10 10  12 13 14 15 16    14 15 17 20 22  19 21 24 27 30  13 14 15 16 17  20 21 22 24 25
 8  8  9 11 12  10 12 13 15 17   7  7  7  8  8  10 11 11 12 13    11 12 14 16 18  15 17 19 22 25  11 11 12 13 14  16 17 19 20 21

# Age 60-64
13 15 17 19 22  19 22 24 28 32  11 11 12 13 14  17 19 20 21 23    20 23 26 30 34  29 33 37 42 47  18 19 21 22 24  29 31 33 36 38
11 12 14 15 18  15 17 20 23 26   9  9 10 11 12  14 15 16 18 19    16 19 21 24 28  24 27 30 35 39  15 16 17 18 20  24 26 28 30 32
 9 10 11 12 14  12 14 16 18 21   7  8  8  9  9  12 13 14 15 16    13 15 17 20 22  19 22 25 28 32  12 13 14 15 16  20 21 23 25 27
 7  8  9 10 11  10 11 13 15 17   6  6  7  7  8  10 10 11 12 13    11 12 14 16 18  15 18 20 23 27  10 11 12 12 13  16 18 19 21 23
 5  6  7  8  9   8  9 10 12 14   5  5  5  6  6   8  8  9 10 11     8 10 11 13 15  12 14 16 19 22   8  9  9 10 11  14 15 16 17 19

# Age 55-59
10 12 13 15 18  16 18 21 24 27   8  9  9 10 11  14 16 17 18 20    17 19 22 25 29  25 29 33 38 44  15 16 17 19 20  26 28 30 33 36
 8  9 11 12 14  12 14 16 19 22   7  7  8  8  9  12 13 14 15 16    13 15 17 20 23  20 23 27 31 36  12 13 14 15 17  21 23 25 27 30
 6  7  8  9 11  10 11 13 15 18   5  6  6  7  7   9 10 11 12 13    10 12 14 16 19  16 19 21 25 29  10 10 11 12 13  17 19 20 22 25
 5  6  6  7  9   8  9 10 12 14   4  4  5  5  6   7  8  9 10 11     8  9 11 13 15  13 15 17 20 23   8  8  9 10 11  14 15 17 18 20
 4  4  5  6  7   6  7  8  9 11   3  4  4  4  5   6  6  7  8  9     6  7  8 10 12  10 12 13 16 19   6  7  7  8  9  11 12 13 15 16

# Age 50-54
 8  9 11 12 14  13 15 17 20 24   6  7  7  8  9  12 13 14 16 17    14 16 18 21 25  22 26 30 35 40  12 13 14 16 17  23 25 27 30 33
 6  7  8  9 11  10 12 14 16 19   5  5  6  6  7   9 10 11 13 14    11 12 14 17 20  18 20 24 28 32  10 10 11 13 14  18 20 22 25 27
 5  5  6  7  9   8  9 10 12 15   4  4  5  5  5   7  8  9 10 11     8 10 11 13 15  14 16 18 22 26   7  8  9 10 11  15 16 18 20 22
 4  4  5  6  7   6  7  8  9 11   3  3  4  4  4   6  6  7  8  9     6  7  9 10 12  11 12 14 17 20   6  6  7  8  9  12 13 14 16 18
 3  3  4  4  5   5  5  6  7  9   2  3  3  3  3   5  5  6  6  7     5  6  7  8  9   8  9 11 13 16   5  5  6  6  7   9 10 11 13 14

# Age 45-49
 6  7  8 10 11  11 13 15 17 21   5  5  6  6  7  10 11 12 13 15    12 13 15 18 21  20 23 27 31 37  10 11 12 13 15  20 22 25 28 31
 5  5  6  7  9   8  9 11 13 16   4  4  4  5  5   8  8  9 10 12     9 10 12 14 16  15 18 21 25 29   8  8  9 10 12  16 18 20 22 25
 4  4  5  6  7   6  7  8 10 12   3  3  3  4  4   6  7  7  8  9     7  8  9 11 13  12 13 16 19 23   6  6  7  8  9  12 14 16 18 20
 3  3  4  4  5   5  5  6  8  9   2  2  3  3  3   5  5  6  6  7     5  6  7  8 10   9 10 12 15 18   4  5  6  6  7  10 11 12 14 16
 2  2  3  3  4   3  4  5  6  7   2  2  2  2  2   3  4  4  5  6     4  4  5  6  7   7  8  9 11 14   3  4  4  5  5   8  8 10 11 12

# Age 40-44
 5  6  7  8  9   9 10 12 15 18   4  4  4  5  6   8  9 10 11 13    10 11 13 15 18  17 20 24 28 34   8  9 10 11 13  18 20 23 25 29
 4  4  5  6  7   7  8  9 11 13   3  3  3  4  4   6  7  8  9 10     7  8 10 11 14  13 15 18 22 27   6  7  8  9 10  14 16 18 20 23
 3  3  4  4  5   5  6  7  8 10   2  2  3  3  3   5  5  6  7  8     5  6  7  9 10  10 11 14 17 20   5  5  6  7  7  11 12 14 16 18
 2  2  3  3  4   4  4  5  6  8   2  2  2  2  2   3  4  4  5  6     4  5  5  6  8   7  9 10 12 15   3  4  4  5  6   8  9 11 12 14
 1  2  2  2  3   3  3  4  5  6   1  1  1  2  2   3  3  3  4  5     3  3  4  5  6   5  6  8  9 12   3  3  4  4  4   6  7  8  9 11
"""

raw_nonlab_data = """
# Age 70-74
24 26 28 30 32  31 33 35 37 40  21 21 22 23 24  29 30 31 32 33
20 22 23 25 27  26 28 30 32 34  17 18 19 19 20  25 26 26 27 28
17 18 19 21 22  22 23 25 27 28  15 15 16 16 17  21 22 22 23 24
14 15 16 17 18  18 19 21 22 24  12 13 13 14 14  18 18 19 20 20
11 12 13 14 15  15 16 17 18 20  10 11 11 12 12  15 15 16 17 17

# Age 65-69
19 20 22 24 26  26 28 30 33 36  16 17 18 18 19  25 26 27 28 29
15 17 18 20 22  21 23 25 27 30  13 14 14 15 16  21 21 22 23 24
12 14 15 16 18  17 19 21 22 25  11 11 12 12 13  17 18 19 19 20
10 11 12 13 14  14 15 17 18 20   9  9 10 10 11  14 15 15 16 17
 8  9 10 11 12  11 12 14 15 16   7  8  8  8  9  12 12 13 13 14

# Age 60-64
15 16 18 20 22  21 24 26 29 32  13 13 14 14 15  21 22 23 24 26
12 13 14 16 18  17 19 21 24 26  10 11 11 12 12  17 18 19 20 21
 9 10 11 13 14  14 15 17 19 21   8  9  9  9 10  14 15 15 16 17
 7  8  9 10 11  11 12 14 15 17   7  7  7  8  8  11 12 12 13 14
 6  6  7  8  9   9 10 11 12 13   5  5  6  6  6   9  9 10 11 11

# Age 55-59
11 13 14 16 18  18 20 23 26 29  10 10 11 11 12  18 19 20 21 22
 9 10 11 13 14  14 16 18 20 23   8  8  9  9 10  14 15 16 17 18
 7  8  9 10 11  11 12 14 16 18   6  6  7  7  7  11 12 13 13 14
 5  6  7  8  9   9 10 11 12 14   5  5  5  6  6   9  9 10 11 11
 4  5  5  6  7   7  7  8 10 11   4  4  4  4  5   7  7  8  8  9

# Age 50-54
 9 10 11 13 15  15 17 20 22 26   8  8  9  9 10  15 16 17 18 19
 7  8  9 10 11  11 13 15 17 20   6  6  7  7  7  12 13 13 14 15
 5  6  7  8  9   9 10 12 13 15   5  5  5  5  6   9 10 10 11 12
 4  4  5  6  7   7  8  9 10 12   3  4  4  4  4   7  7  8  9  9
 3  3  4  4  5   5  6  7  8  9   3  3  3  3  3   5  6  6  7  7

# Age 45-49
 7  8  9 11 12  12 14 17 20 23   6  6  7  7  8  13 14 15 16 17
 5  6  7  8  9   9 11 13 15 17   5  5  5  5  6  10 10 11 12 13
 4  4  5  6  7   7  8  9 11 13   3  4  4  4  4   7  8  8  9 10
 3  3  4  4  5   5  6  7  8 10   2  3  3  3  3   6  6  6  7  7
 2  2  3  3  4   4  4  5  6  7   2  2  2  2  2   4  4  5  5  6

# Age 40-44
 5  6  7  9 10  10 12 14 17 20   5  5  5  6  6  11 12 13 14 15
 4  5  5  6  7   8  9 11 13 15   3  4  4  4  4   8  9  9 10 11
 3  3  4  5  5   5  6  8  9 11   2  3  3  3  3   6  6  7  7  8
 2  2  3  3  4   4  5  6  7  8   2  2  2  2  2   4  5  5  6  6
 2  2  2  2  3   3  3  4  5  6   1  1  1  2  2   3  3  4  4  4
"""

def parse_charts():
    data = {
        "lab_based": {},
        "non_lab_based": {}
    }
    
    age_bands = ["70-74", "65-69", "60-64", "55-59", "50-54", "45-49", "40-44"]
    sbp_bands = [">=180", "160-179", "140-159", "120-139", "<120"]
    chol_bands = ["<4", "4-4.9", "5-5.9", "6-6.9", ">=7"]
    bmi_bands = ["<20", "20-24", "25-29", "30-34", ">=35"]
    
    for d in ["diabetes_no", "diabetes_yes"]:
        data["lab_based"][d] = {"male": {"non_smoker": {}, "smoker": {}}, "female": {"non_smoker": {}, "smoker": {}}}
        # Note: Non-lab chart doesn't have diabetes specific columns explicitly?
        # WAIT! Let me look at south-asia-2.png. 
        # Ah, south-asia-2.png does not have a "People with Diabetes" half!!
        # Let me double check the image. Yes! It's just one block for "Non-laboratory based risk chart".
        # This implies it applies regardless of diabetes, or it doesn't account for diabetes.
        # But wait, WHO non-lab chart doesn't use diabetes? No, let's keep the structure but copy the same data if it doesn't have it, or just use a single structure.
        # I'll populate the non_lab_based in a similar way, duplicating for diabetes_yes/no to keep the interface simple.
        data["non_lab_based"][d] = {"male": {"non_smoker": {}, "smoker": {}}, "female": {"non_smoker": {}, "smoker": {}}}

    # Parse Lab Based
    lines = [l for l in raw_lab_data.split('\n') if l.strip()]
    age_idx = -1
    sbp_idx = 0
    for line in lines:
        if line.strip().startswith("#"):
            age_idx += 1
            sbp_idx = 0
            continue
        
        nums = [int(x) for x in line.split()]
        if len(nums) != 40:
            print("ERROR Lab", len(nums), line)
            continue
            
        age = age_bands[age_idx]
        sbp = sbp_bands[sbp_idx]
        
        # diabetes_no
        dm_no_m_ns = nums[0:5]
        dm_no_m_s = nums[5:10]
        dm_no_w_ns = nums[10:15]
        dm_no_w_s = nums[15:20]
        
        # diabetes_yes
        dm_yes_m_ns = nums[20:25]
        dm_yes_m_s = nums[25:30]
        dm_yes_w_ns = nums[30:35]
        dm_yes_w_s = nums[35:40]
        
        def assign(dm_key, sex_key, smoker_key, chol_arr):
            if age not in data["lab_based"][dm_key][sex_key][smoker_key]:
                data["lab_based"][dm_key][sex_key][smoker_key][age] = {}
            if sbp not in data["lab_based"][dm_key][sex_key][smoker_key][age]:
                data["lab_based"][dm_key][sex_key][smoker_key][age][sbp] = {}
            for i, val in enumerate(chol_arr):
                data["lab_based"][dm_key][sex_key][smoker_key][age][sbp][chol_bands[i]] = f"{val}%"

        assign("diabetes_no", "male", "non_smoker", dm_no_m_ns)
        assign("diabetes_no", "male", "smoker", dm_no_m_s)
        assign("diabetes_no", "female", "non_smoker", dm_no_w_ns)
        assign("diabetes_no", "female", "smoker", dm_no_w_s)
        
        assign("diabetes_yes", "male", "non_smoker", dm_yes_m_ns)
        assign("diabetes_yes", "male", "smoker", dm_yes_m_s)
        assign("diabetes_yes", "female", "non_smoker", dm_yes_w_ns)
        assign("diabetes_yes", "female", "smoker", dm_yes_w_s)
        
        sbp_idx += 1

    # Parse Non-Lab Based
    lines = [l for l in raw_nonlab_data.split('\n') if l.strip()]
    age_idx = -1
    sbp_idx = 0
    for line in lines:
        if line.strip().startswith("#"):
            age_idx += 1
            sbp_idx = 0
            continue
            
        nums = [int(x) for x in line.split()]
        if len(nums) != 20:
            print("ERROR Non-Lab", len(nums), line)
            continue
            
        age = age_bands[age_idx]
        sbp = sbp_bands[sbp_idx]
        
        m_ns = nums[0:5]
        m_s = nums[5:10]
        w_ns = nums[10:15]
        w_s = nums[15:20]
        
        def assign_nl(sex_key, smoker_key, bmi_arr):
            for dm_key in ["diabetes_no", "diabetes_yes"]:
                if age not in data["non_lab_based"][dm_key][sex_key][smoker_key]:
                    data["non_lab_based"][dm_key][sex_key][smoker_key][age] = {}
                if sbp not in data["non_lab_based"][dm_key][sex_key][smoker_key][age]:
                    data["non_lab_based"][dm_key][sex_key][smoker_key][age][sbp] = {}
                for i, val in enumerate(bmi_arr):
                    data["non_lab_based"][dm_key][sex_key][smoker_key][age][sbp][bmi_bands[i]] = f"{val}%"

        assign_nl("male", "non_smoker", m_ns)
        assign_nl("male", "smoker", m_s)
        assign_nl("female", "non_smoker", w_ns)
        assign_nl("female", "smoker", w_s)
        
        sbp_idx += 1

    with open("c:\\\\NUV\\\\tetrathon\\\\who_cvd_charts.json", "w") as f:
        json.dump(data, f, indent=2)
    print("who_cvd_charts.json rewritten with full data.")

if __name__ == "__main__":
    parse_charts()
