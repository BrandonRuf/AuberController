program_set = dict()

def program(name, operation):
    if name in program_set.keys():
        myprogram = program_set[name]
        myprogram.append(operation)
    else:
        program_set[name] = list()
        program_set[name].append(operation)


program("YBa2Cu3O7-x",['Ramp',950, 0.1])
program("YBa2Cu3O7-x",['Soak',950, 2])
program("YBa2Cu3O7-x",['Ramp',800, 2])
program("YBa2Cu3O7-x",['Ramp',300, 10])
program("YBa2Cu3O7-x",['Ramp',25, 4])

# for EuMnSb2 growth 23-Oct-2020 - NOT WHAT WAS USED!
program("EuMnSb2",['Ramp',650,3])
program("EuMnSb2",['Soak',650,1])
program("EuMnSb2",['Ramp',900,3])
program("EuMnSb2",['Soak',900,75])
program("EuMnSb2",['Ramp',20,3])


program("GaAs",['Ramp', 50, 0.12])
program("GaAs",["Soak", 50, 0.13])
program("GaAs",["Ramp", 34, 0.1])
program("GaAs",["Ramp", 25, .5])

program("(δ-phase) Pu-Ga",['Ramp', 639.4, 1])
program("(δ-phase) Pu-Ga",["Soak", 639.4, .3])
program("(δ-phase) Pu-Ga",["Ramp", 25, 1])


