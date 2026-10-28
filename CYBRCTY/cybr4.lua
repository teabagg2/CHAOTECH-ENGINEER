
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")

local SaveStore = DataStoreService:GetDataStore("CyberCity_Save_V2")

local STARTING_CREDITS = 500
local INCOME_INTERVAL = 5
local AUTOSAVE_INTERVAL = 60
local VIP_MULTIPLIER = 2
local PLOT_SPACING = 120
local MAX_LEVEL = 3

local BUSINESSES = {
    {
        Id = "ServerHub",
        Name = "SERVER HUB",
        Description = "Your first technology business",
        Cost = 250,
        BaseIncome = 25,
        Color = Color3.fromRGB(0, 220, 255),
        Position = Vector3.new(-25, 0, -10)
    },
    {
        Id = "CyberCafe",
        Name = "CYBER CAFE",
        Description = "A futuristic gaming cafe",
        Cost = 1500,
        BaseIncome = 100,
        Color = Color3.fromRGB(180, 70, 255),
        Position = Vector3.new(25, 0, -10)
    },
    {
        Id = "DataCenter",
        Name = "DATA CENTER",
        Description = "Power the digital world",
        Cost = 5000,
        BaseIncome = 300,
        Color = Color3.fromRGB(0, 255, 150),
        Position = Vector3.new(-25, 0, 25)
    },
    {
        Id = "AILaboratory",
        Name = "AI LABORATORY",
        Description = "Build the next generation of AI",
        Cost = 15000,
        BaseIncome = 800,
        Color = Color3.fromRGB(255, 170, 0),
        Position = Vector3.new(25, 0, 25)
    }
}

local LEVEL_COSTS = {
    [1] = 500,
    [2] = 1500
}

local LEVEL_MULTIPLIERS = {
    [1] = 1,
    [2] = 3,
    [3] = 7
}

local playerStates = {}
local savingPlayers = {}
local nextPlot = 0

local function makePart(parent, name, size, position, color, material, anchored, canCollide)
    local part = Instance.new("Part")
    part.Name = name
    part.Size = size
    part.Position = position
    part.Color = color
    part.Material = material or Enum.Material.SmoothPlastic
    part.Anchored = anchored ~= false
    part.CanCollide = canCollide ~= false
    part.TopSurface = Enum.SurfaceType.Smooth
    part.BottomSurface = Enum.SurfaceType.Smooth
    part.Parent = parent
    return part
end

local function makeLabel(part, text, color)
    local gui = Instance.new("BillboardGui")
    gui.Name = "BusinessLabel"
    gui.Size = UDim2.new(0, 220, 0, 55)
    gui.StudsOffset = Vector3.new(0, 5, 0)
    gui.AlwaysOnTop = true
    gui.Parent = part

    local label = Instance.new("TextLabel")
    label.Size = UDim2.fromScale(1, 1)
    label.BackgroundTransparency = 1
    label.Text = text
    label.TextColor3 = color
    label.TextStrokeTransparency = 0.25
    label.Font = Enum.Font.GothamBold
    label.TextScaled = true
    label.Parent = gui
end

local function getBusinessDefinition(businessId)
    for _, definition in ipairs(BUSINESSES) do
        if definition.Id == businessId then
            return definition
        end
    end
    return nil
end

local function getIncome(definition, level)
    return definition.BaseIncome * (LEVEL_MULTIPLIERS[level] or 1)
end

local function getTotalIncome(state)
    local total = 0

    for businessId, owned in pairs(state.OwnedBusinesses) do
        if owned then
            local definition = getBusinessDefinition(businessId)
            local level = state.BusinessLevels[businessId] or 1

            if definition then
                total += getIncome(definition, level)
            end
        end
    end

    return total
end

local function updateLeaderstats(player)
    local state = playerStates[player.UserId]
    if not state then
        return
    end

    local leaderstats = player:FindFirstChild("leaderstats")
    if not leaderstats then
        return
    end

    local credits = leaderstats:FindFirstChild("Credits")
    if credits then
        credits.Value = state.Credits
    end
end

local function addCredits(player, amount)
    local state = playerStates[player.UserId]
    if not state then
        return
    end

    state.Credits += amount
    updateLeaderstats(player)
end

local function setCredits(player, amount)
    local state = playerStates[player.UserId]
    if not state then
        return
    end

    state.Credits = amount
    updateLeaderstats(player)
end

local function createBusinessBuilding(plot, origin, definition, level)
    local folder = plot:FindFirstChild("Businesses")
    if not folder then
        folder = Instance.new("Folder")
        folder.Name = "Businesses"
        folder.Parent = plot
    end

    local old = folder:FindFirstChild(definition.Id)
    if old then
        old:Destroy()
    end

    local model = Instance.new("Model")
    model.Name = definition.Id
    model.Parent = folder

    local basePosition = origin + definition.Position

    local height = 8 + level * 4
    local width = 18 + level * 2
    local depth = 18 + level * 2

    local building = makePart(
        model,
        "Building",
        Vector3.new(width, height, depth),
        basePosition + Vector3.new(0, height / 2 + 0.5, 0),
        definition.Color,
        Enum.Material.Metal,
        true,
        true
    )

    model.PrimaryPart = building

    makePart(
        model,
        "Roof",
        Vector3.new(width + 2, 1, depth + 2),
        basePosition + Vector3.new(0, height + 1, 0),
        Color3.fromRGB(12, 18, 35),
        Enum.Material.Neon,
        true,
        false
    )

    makePart(
        model,
        "FrontWindow",
        Vector3.new(width * 0.65, height * 0.35, 0.4),
        basePosition + Vector3.new(0, height * 0.55, -depth / 2 - 0.25),
        definition.Color,
        Enum.Material.Neon,
        true,
        false
    )

    makePart(
        model,
        "Door",
        Vector3.new(3, height * 0.4, 0.5),
        basePosition + Vector3.new(0, height * 0.2, -depth / 2 - 0.3),
        Color3.fromRGB(5, 10, 20),
        Enum.Material.Glass,
        true,
        false
    )

    makeLabel(
        building,
        definition.Name .. "\nLEVEL " .. level,
        definition.Color
    )

    return model
end

local function getPlotOrigin(state)
    return Vector3.new(state.PlotIndex * PLOT_SPACING, 0, 0)
end

local function createPrompt(part, actionText, objectText, holdDuration)
    local prompt = Instance.new("ProximityPrompt")
    prompt.ActionText = actionText
    prompt.ObjectText = objectText
    prompt.HoldDuration = holdDuration or 0.5
    prompt.MaxActivationDistance = 12
    prompt.RequiresLineOfSight = false
    prompt.Parent = part
    return prompt
end

local function refreshPlot(player)
    local state = playerStates[player.UserId]
    if not state or not state.Plot then
        return
    end

    local plot = state.Plot
    local origin = getPlotOrigin(state)

    local businessesFolder = plot:FindFirstChild("Businesses")
    if businessesFolder then
        businessesFolder:Destroy()
    end

    local controlsFolder = plot:FindFirstChild("BusinessControls")
    if controlsFolder then
        controlsFolder:Destroy()
    end

    businessesFolder = Instance.new("Folder")
    businessesFolder.Name = "Businesses"
    businessesFolder.Parent = plot

    controlsFolder = Instance.new("Folder")
    controlsFolder.Name = "BusinessControls"
    controlsFolder.Parent = plot

    for index, definition in ipairs(BUSINESSES) do
        local controlPosition = origin + definition.Position
            + Vector3.new(0, 0, 13)

        local control = makePart(
            controlsFolder,
            definition.Id .. "Control",
            Vector3.new(10, 2, 3),
            controlPosition + Vector3.new(0, 1, 0),
            definition.Color,
            Enum.Material.Neon,
            true,
            true
        )

        local owned = state.OwnedBusinesses[definition.Id] == true
        local level = state.BusinessLevels[definition.Id] or 1

        if owned then
            createBusinessBuilding(plot, origin, definition, level)

            local upgradeCost = LEVEL_COSTS[level]
            local actionText

            if level >= MAX_LEVEL then
                actionText = "MAX LEVEL"
            else
                actionText = "Upgrade: " .. upgradeCost .. " Credits"
            end

            makeLabel(
                control,
                definition.Name .. "\nIncome: "
                    .. getIncome(definition, level) .. " / 5 sec",
                definition.Color
            )

            local prompt = createPrompt(
                control,
                actionText,
                definition.Name
            )

            prompt.Triggered:Connect(function(triggeringPlayer)
                if triggeringPlayer ~= player then
                    return
                end

                local currentState = playerStates[player.UserId]
                if not currentState then
                    return
                end

                local currentLevel =
                    currentState.BusinessLevels[definition.Id] or 1

                if currentLevel >= MAX_LEVEL then
                    return
                end

                local cost = LEVEL_COSTS[currentLevel]
                if not cost or currentState.Credits < cost then
                    return
                end

                setCredits(player, currentState.Credits - cost)
                currentState.BusinessLevels[definition.Id] = currentLevel + 1
                refreshPlot(player)
            end)
        else
            makeLabel(
                control,
                definition.Name .. "\nCost: " .. definition.Cost .. " Credits",
                definition.Color
            )

            local prompt = createPrompt(
                control,
                "Buy: " .. definition.Cost .. " Credits",
                definition.Name
            )

            prompt.Triggered:Connect(function(triggeringPlayer)
                if triggeringPlayer ~= player then
                    return
                end

                local currentState = playerStates[player.UserId]
                if not currentState then
                    return
                end

                if currentState.OwnedBusinesses[definition.Id] then
                    return
                end

                if index > 1 then
                    local previousDefinition = BUSINESSES[index - 1]
                    if not currentState.OwnedBusinesses[previousDefinition.Id] then
                        return
                    end
                end

                if currentState.Credits < definition.Cost then
                    return
                end

                setCredits(player, currentState.Credits - definition.Cost)
                currentState.OwnedBusinesses[definition.Id] = true
                currentState.BusinessLevels[definition.Id] = 1

                if definition.Id == "ServerHub" then
                    currentState.OwnsServer = true
                    currentState.BusinessLevel = 1
                end

                refreshPlot(player)
            end)
        end
    end
end

local function createPlot(player)
    local state = playerStates[player.UserId]
    if not state then
        return
    end

    nextPlot += 1
    state.PlotIndex = nextPlot

    local origin = getPlotOrigin(state)
    local plot = Instance.new("Model")
    plot.Name = "CyberCity_" .. player.UserId
    plot.Parent = workspace
    state.Plot = plot

    local ground = makePart(
        plot,
        "PlotGround",
        Vector3.new(100, 4, 100),
        origin + Vector3.new(0, -1.5, 0),
        Color3.fromRGB(17, 24, 40),
        Enum.Material.Concrete,
        true,
        true
    )

    plot.PrimaryPart = ground

    local borderColor = Color3.fromRGB(0, 220, 255)

    for _, border in ipairs({
        {Vector3.new(100, 1, 1), Vector3.new(0, 0.6, -50)},
        {Vector3.new(100, 1, 1), Vector3.new(0, 0.6, 50)},
        {Vector3.new(1, 1, 100), Vector3.new(-50, 0.6, 0)},
        {Vector3.new(1, 1, 100), Vector3.new(50, 0.6, 0)}
    }) do
        makePart(
            plot,
            "NeonBorder",
            border[1],
            origin + border[2],
            borderColor,
            Enum.Material.Neon,
            true,
            false
        )
    end

    local sign = makePart(
        plot,
        "OwnerSign",
        Vector3.new(24, 7, 1),
        origin + Vector3.new(0, 5, -43),
        Color3.fromRGB(8, 14, 30),
        Enum.Material.Metal,
        true,
        true
    )

    makeLabel(
        sign,
        player.DisplayName .. "'S CYBER CITY",
        borderColor
    )

    refreshPlot(player)
end

local function positionCharacter(player, character)
    local state = playerStates[player.UserId]
    if not state then
        return
    end

    local root = character:WaitForChild("HumanoidRootPart", 10)
    local humanoid = character:WaitForChild("Humanoid", 10)

    if not root or not humanoid then
        return
    end

    task.wait(0.2)

    local origin = getPlotOrigin(state)
    character:PivotTo(CFrame.new(origin + Vector3.new(0, 7, 12)))

    root.Anchored = false
    root.AssemblyLinearVelocity = Vector3.zero
    root.AssemblyAngularVelocity = Vector3.zero

    humanoid.WalkSpeed = 16
    humanoid.JumpPower = 50
    humanoid.AutoRotate = true
    humanoid.PlatformStand = false
    humanoid.Sit = false

    pcall(function()
        humanoid:ChangeState(Enum.HumanoidStateType.GettingUp)
    end)
end

local function normalizeSave(data)
    data = type(data) == "table" and data or {}

    local credits = tonumber(data.Credits) or STARTING_CREDITS
    local ownsServer = data.OwnsServer == true
    local businessLevel = math.clamp(
        tonumber(data.BusinessLevel) or 1,
        1,
        MAX_LEVEL
    )

    local ownedBusinesses = {}
    local businessLevels = {}

    if type(data.OwnedBusinesses) == "table" then
        for businessId, owned in pairs(data.OwnedBusinesses) do
            if getBusinessDefinition(businessId) and owned == true then
                ownedBusinesses[businessId] = true
            end
        end
    end

    if type(data.BusinessLevels) == "table" then
        for businessId, level in pairs(data.BusinessLevels) do
            if getBusinessDefinition(businessId) then
                businessLevels[businessId] = math.clamp(
                    tonumber(level) or 1,
                    1,
                    MAX_LEVEL
                )
            end
        end
    end

    if ownsServer then
        ownedBusinesses.ServerHub = true
        businessLevels.ServerHub = businessLevel
    end

    for businessId in pairs(ownedBusinesses) do
        businessLevels[businessId] = businessLevels[businessId] or 1
    end

    return {
        Credits = math.max(0, credits),
        OwnsServer = ownedBusinesses.ServerHub == true,
        BusinessLevel = businessLevels.ServerHub or 1,
        OwnedBusinesses = ownedBusinesses,
        BusinessLevels = businessLevels
    }
end

local function savePlayer(player)
    local userId = player.UserId
    local state = playerStates[userId]

    if not state or savingPlayers[userId] then
        return false
    end

    savingPlayers[userId] = true

    local saveData = {
        Credits = state.Credits,
        OwnsServer = state.OwnedBusinesses.ServerHub == true,
        BusinessLevel = state.BusinessLevels.ServerHub or 1,
        OwnedBusinesses = state.OwnedBusinesses,
        BusinessLevels = state.BusinessLevels
    }

    local success, err = pcall(function()
        SaveStore:UpdateAsync("Player_" .. userId, function()
            return saveData
        end)
    end)

    savingPlayers[userId] = nil

    if not success then
        warn("Cyber City save failed for " .. player.Name .. ": " .. tostring(err))
    end

    return success
end

local function loadPlayer(player)
    local success, data = pcall(function()
        return SaveStore:GetAsync("Player_" .. player.UserId)
    end)

    if not success then
        warn("Cyber City data load failed for " .. player.Name .. ": " .. tostring(data))
        player:Kick("Your saved city could not load. Please check the experience and try again.")
        return
    end

    local saved = normalizeSave(data)

    playerStates[player.UserId] = {
        Credits = saved.Credits,
        OwnsServer = saved.OwnsServer,
        BusinessLevel = saved.BusinessLevel,
        OwnedBusinesses = saved.OwnedBusinesses,
        BusinessLevels = saved.BusinessLevels,
        PlotIndex = 0,
        Plot = nil
    }

    local leaderstats = Instance.new("Folder")
    leaderstats.Name = "leaderstats"
    leaderstats.Parent = player

    local credits = Instance.new("IntValue")
    credits.Name = "Credits"
    credits.Value = saved.Credits
    credits.Parent = leaderstats

    createPlot(player)

    player.CharacterAdded:Connect(function(character)
        positionCharacter(player, character)
    end)

    if player.Character then
        task.spawn(positionCharacter, player, player.Character)
    end
end

Players.PlayerAdded:Connect(function(player)
    task.spawn(loadPlayer, player)
end)

for _, player in ipairs(Players:GetPlayers()) do
    task.spawn(loadPlayer, player)
end

Players.PlayerRemoving:Connect(function(player)
    savePlayer(player)

    local state = playerStates[player.UserId]
    if state and state.Plot then
        state.Plot:Destroy()
    end

    playerStates[player.UserId] = nil
end)

task.spawn(function()
    while true do
        task.wait(INCOME_INTERVAL)

        for _, player in ipairs(Players:GetPlayers()) do
            local state = playerStates[player.UserId]

            if state then
                local income = getTotalIncome(state)

                if player:GetAttribute("CyberCityVIP") == true then
                    income *= VIP_MULTIPLIER
                end

                if income > 0 then
                    addCredits(player, income)
                end
            end
        end
    end
end)

task.spawn(function()
    while true do
        task.wait(AUTOSAVE_INTERVAL)

        for _, player in ipairs(Players:GetPlayers()) do
            task.spawn(savePlayer, player)
        end
    end
end)

game:BindToClose(function()
    local pending = 0

    for _, player in ipairs(Players:GetPlayers()) do
        pending += 1

        task.spawn(function()
            local deadline = os.clock() + 20

            while savingPlayers[player.UserId] and os.clock() < deadline do
                task.wait(0.1)
            end

            savePlayer(player)
            pending -= 1
        end)
    end

    local deadline = os.clock() + 25

    while pending > 0 and os.clock() < deadline do
        task.wait(0.1)
    end
end)

print("Cyber City Tycoon progression system loaded.")
