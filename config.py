import duckdb
import polars as pl
import datetime
import concurrent.futures

con = duckdb.connect("google_sheets_pipeline.duckdb")

def GetWeaponAttackPower(weapon_of_choice, weapon_upgrade, stats, df, df_bin, df_weapon):
    
    def GetCalcCorrectFormulaInputs(stats, df):
        results = {}
        for stat in stats:
            input = stats[stat]
            if input <= df['stat_1'][0]:
                posmin = 0
                posmax = 1
            elif input <= df['stat_2'][0]:
                posmin = 1
                posmax = 2
            elif input <= df['stat_3'][0]:
                posmin = 2
                posmax = 3
            elif input <= df['stat_4'][0]:
                posmin = 3
                posmax = 4
        
            statmin = df[f'stat_{posmin}'][0]
            statmax = df[f'stat_{posmax}'][0]
            growmin = df[f'grow_{posmin}'][0]
            growmax = df[f'grow_{posmax}'][0]
            exponentmin = df[f'exponent_{posmin}'][0]
    
            results[f'{stat}'] = {
                'input': input, 
                'statmin': statmin, 
                'statmax': statmax, 
                'growmin': growmin, 
                'growmax': growmax, 
                'exponentmin': exponentmin
            }
            
        return results
    
    def CalcCorrectFormula(stat_payload):
    
        input = stat_payload['input']
        statmin = stat_payload['statmin']
        statmax = stat_payload['statmax']
        growmin = stat_payload['growmin']
        growmax = stat_payload['growmax']
        exponentmin = stat_payload['exponentmin']
        
        ratio = (input - statmin) / (statmax - statmin)
        
        if exponentmin > 0:
            growth = ratio ** exponentmin
            
        if exponentmin < 0:
            growth = 1 - (1 - ratio) ** abs(exponentmin)
    
        result = growmin + ((growmax - growmin) * growth)
        
        return result
    
    def GetDamageByStats(df, stats):
        results = {}
        for i in df['damage_type']:
            for stat in stats:
                if df_bin[f'{i}_scaling_{stat[:3]}'][0] == 1:
                    formula_inputs = GetCalcCorrectFormulaInputs(stats, df.filter(pl.col('damage_type') == i))
                    formula_output = CalcCorrectFormula(formula_inputs[stat]) / 100
                    if formula_output > 0:
                        results[f'stat_multiplier_{i}_on_{stat}'] = formula_output
        # Converte o dict para um DataFrame polars
        return pl.DataFrame(list(results.items()), schema=['stat', 'value'])
    
    def FinalScalingCalc(df, df_weapon):
        results = {}
        for i in df.columns:
            join = i.replace('stat_multiplier_', '')
            if join in df_weapon.columns:
                result = df_weapon[f'{join}_scaling'][0] * df[i][0]
                if result > 0:
                    results[f'scaled_{i.split("_")[2]}_attack_on_{i.split("_")[4]}'] = result
        # Converte o dict para um DataFrame polars
        return pl.DataFrame(list(results.items()), schema=['scaled_stat', 'value'])
    
    def TotalAttackPower(results_df):
        physical_attack = df_weapon['upgraded_weapon_physical_attack'][0]
        magic_attack = df_weapon['upgraded_weapon_magic_attack'][0]
        fire_attack = df_weapon['upgraded_weapon_fire_attack'][0]
        lightning_attack = df_weapon['upgraded_weapon_lightning_attack'][0]
        
        for i in results_df['scaled_stat']:
            stat_name = i.split('_')[1]
            if stat_name == 'physical':
                physical_attack += results_df.filter(pl.col('scaled_stat') == i)['value'][0]
            if stat_name == 'magic':
                magic_attack += results_df.filter(pl.col('scaled_stat') == i)['value'][0]
            if stat_name == 'fire':
                fire_attack += results_df.filter(pl.col('scaled_stat') == i)['value'][0]
            if stat_name == 'lightning':
                lightning_attack += results_df.filter(pl.col('scaled_stat') == i)['value'][0]
        
        total_weapon_attack_power = physical_attack + magic_attack + fire_attack + lightning_attack
        return total_weapon_attack_power
    
    return TotalAttackPower(FinalScalingCalc(GetDamageByStats(df, stats), df_weapon))

def GetAllData(stats, weapon_upgrade):
    all_weapons = con.sql("SELECT * FROM main.all_weapons").pl()
    df_weapon_src = con.sql("SELECT * FROM main.df_weapon_src").pl()
    df_src = con.sql("SELECT * FROM main.df_src").pl()
    df_bin_src = con.sql("SELECT * FROM main.df_bin_src").pl()
    
    final_damages = {}
    
    def process_weapon(weapon_name):
        print(weapon_name)
        print(datetime.datetime.now())
        try:
            df_weapon = df_weapon_src.filter(pl.col('name') == weapon_name).to_pandas().reset_index()
            df_weapon = pl.from_pandas(df_weapon.loc[[weapon_upgrade]])
            df = df_src.filter(pl.col('name') == weapon_name)
            df_bin = df_bin_src.filter(pl.col('name') == weapon_name)

            result = GetWeaponAttackPower(weapon_name, weapon_upgrade, stats, df, df_bin, df_weapon)
            return weapon_name, result
        except Exception as e:
            print(f"Error processing weapon {weapon_name}: {e}")
            return weapon_name, None
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_weapon, weapon_name) for weapon_name in all_weapons['name']]
        for future in concurrent.futures.as_completed(futures):
            weapon_name, result = future.result()
            if result is not None:
                final_damages[weapon_name] = result

    sorted_data_desc = dict(sorted(final_damages.items(), key=lambda item: item[1], reverse=True))
    return sorted_data_desc