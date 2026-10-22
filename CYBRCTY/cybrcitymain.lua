
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local Workspace = game:GetService("Workspace")

local SaveStore = DataStoreService:GetDataStore("CyberCity_Save_V2")

local STARTING_CREDITS = 500
local BUSINESS_COST = 250
local INCOME_INTERVAL = 5
local AUTOSAVE_INTERVAL = 60
local VIP_MULTIPLIER = 2
local PLOT_SPACING = 120
local MAX_LEVEL = 3

local LEVEL_COSTS = {[1] = 500, [2] = 1500}
local LEVEL_INCOME = {[1] = 25, [2] = 75, [3] = 175}

local playerPlots = {}
local playerOrigins = {}
local ownedBusinesses = {}
local businessLevels = {}
local loadedPlayers = {}
local savingPlayers = {}
local nextPlot = 0

local function makePart(parent, name, size, position, color, material, canCollide)
	local part = Instance.new("Part")
	part.Name = name
	part.Size = size
	part.Position = position
	part.Anchored = true
	part.CanCollide = canCollide ~= false
	part.CanTouch = true
	part.CanQuery = true
	part.Color = color
	part.Material = material or Enum.Material.SmoothPlastic
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Parent = parent
	return part
end

local function addSign(parent, name, message, position, size)
	local part = makePart(
		parent, name, size, position,
		Color3.fromRGB(12, 18, 35), Enum.Material.Metal, false
	)

	local gui = Instance.new("SurfaceGui")
	gui.Face = Enum.NormalId.Front
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 35
	gui.Parent = part

	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.Text = message
	label.TextColor3 = Color3.fromRGB(0, 230, 255)
	label.Font = Enum.Font.GothamBold
	label.TextScaled = true
	label.Parent = gui

	return part
end

local function getCredits(player)
	local stats = player:FindFirstChild("leaderstats")
	return stats and stats:FindFirstChild("Credits")
end

local function updateSign(player)
	local plot = playerPlots[player.UserId]
	if not plot then return end

	local sign = plot:FindFirstChild("OwnerSign")
	local gui = sign and sign:FindFirstChildOfClass("SurfaceGui")
	local label = gui and gui:FindFirstChildOfClass("TextLabel")
	local credits = getCredits(player)

	if label then
		label.Text = player.Name .. "'s CYBER CITY\nCredits: "
			.. tostring(credits and credits.Value or 0)
			.. "\nBusiness Level: "
			.. tostring(businessLevels[player.UserId] or 0)
	end
end

local function createCityDecor(plot, origin)
	for i = 1, 4 do
		local height = 12 + i * 7
		makePart(
			plot, "NeonTower" .. i, Vector3.new(8, height, 8),
			origin + Vector3.new(-35 + i * 18, height / 2 + 1, -30),
			Color3.fromRGB(15, 25 + i * 10, 55 + i * 20),
			Enum.Material.Neon
		)
	end

	makePart(
		plot, "NeonRoad", Vector3.new(95, 0.3, 8),
		origin + Vector3.new(0, 0.72, 25),
		Color3.fromRGB(0, 180, 220), Enum.Material.Neon, false
	)

	makePart(
		plot, "NeonRoadCross", Vector3.new(8, 0.32, 75),
		origin + Vector3.new(0, 0.74, 0),
		Color3.fromRGB(120, 0, 255), Enum.Material.Neon, false
	)

	addSign(
		plot, "WelcomeSign", "WELCOME TO CYBER CITY",
		origin + Vector3.new(0, 7, -45), Vector3.new(24, 5, 1)
	)
end

local function createBusiness(plot, origin, level)
	local old = plot:FindFirstChild("PlayerBusiness")
	if old then old:Destroy() end

	local model = Instance.new("Model")
	model.Name = "PlayerBusiness"
	model.Parent = plot

	local height = 10 + level * 8
	local width = 16 + level * 5
	local depth = 16 + level * 5

	makePart(
		model, "Headquarters", Vector3.new(width, height, depth),
		origin + Vector3.new(0, height / 2 + 1, 0),
		Color3.fromRGB(18, 25, 48), Enum.Material.Metal
	)

	makePart(
		model, "Roof", Vector3.new(width + 2, 1, depth + 2),
		origin + Vector3.new(0, height + 1.5, 0),
		Color3.fromRGB(0, 220, 255), Enum.Material.Neon
	)

	makePart(
		model, "Entrance", Vector3.new(5, 7, 1),
		origin + Vector3.new(0, 4.5, depth / 2 + 0.6),
		Color3.fromRGB(0, 140, 200), Enum.Material.Glass, false
	)

	for i = 1, level + 1 do
		makePart(
			model, "Window" .. i, Vector3.new(3, 3, 0.3),
			origin + Vector3.new(
				-width / 2 + i * width / (level + 2),
				height * 0.65 + 1, depth / 2 + 0.2
			),
			Color3.fromRGB(0, 230, 255), Enum.Material.Neon, false
		)
	end

	addSign(
		model, "BusinessSign", "CYBER HQ | LVL " .. level,
		origin + Vector3.new(0, height + 4.5, 0),
		Vector3.new(width, 3, 1)
	)
end

local function savePlayer(player)
	local userId = player.UserId

	if not loadedPlayers[userId] or savingPlayers[userId] then
		return false
	end

	savingPlayers[userId] = true

	local credits = getCredits(player)
	local data = {
		Credits = credits and credits.Value or STARTING_CREDITS,
		OwnsServer = ownedBusinesses[userId] == true,
		BusinessLevel = businessLevels[userId] or 0
	}

	local success, err = pcall(function()
		SaveStore:UpdateAsync("Player_" .. userId, function()
			return data
		end)
	end)

	savingPlayers[userId] = nil

	if not success then
		warn("Cyber City save failed for " .. player.Name .. ": " .. tostring(err))
	end

	return success
end

local function createPlot(player)
	nextPlot += 1

	local origin = Vector3.new((nextPlot - 1) * PLOT_SPACING, 0, 0)
	playerOrigins[player.UserId] = origin

	local plot = Instance.new("Folder")
	plot.Name = "Plot_" .. player.UserId
	plot.Parent = Workspace
	playerPlots[player.UserId] = plot

	makePart(
		plot, "PlotGround", Vector3.new(100, 4, 100),
		origin + Vector3.new(0, -1.5, 0),
		Color3.fromRGB(25, 30, 45), Enum.Material.Concrete
	)

	local borders = {
		{Vector3.new(0, 1.5, -50), Vector3.new(100, 2, 1)},
		{Vector3.new(0, 1.5, 50), Vector3.new(100, 2, 1)},
		{Vector3.new(-50, 1.5, 0), Vector3.new(1, 2, 100)},
		{Vector3.new(50, 1.5, 0), Vector3.new(1, 2, 100)}
	}

	for _, border in ipairs(borders) do
		makePart(
			plot, "PlotBorder", border[2], origin + border[1],
			Color3.fromRGB(0, 220, 255), Enum.Material.Neon
		)
	end

	addSign(
		plot, "OwnerSign", player.Name .. "'s CYBER CITY",
		origin + Vector3.new(0, 5, -42), Vector3.new(18, 5, 1)
	)

	createCityDecor(plot, origin)

	local buyButton = makePart(
		plot, "BuyBusinessButton", Vector3.new(12, 2, 8),
		origin + Vector3.new(-20, 2, 35),
		Color3.fromRGB(0, 200, 100), Enum.Material.Neon
	)

	addSign(
		plot, "BuyBusinessLabel", "BUY BUSINESS\n250 CREDITS",
		buyButton.Position + Vector3.new(0, 2.5, 0),
		Vector3.new(12, 4, 1)
	)

	local buyPrompt = Instance.new("ProximityPrompt")
	buyPrompt.ActionText = "Buy Business"
	buyPrompt.ObjectText = "250 Credits"
	buyPrompt.HoldDuration = 0.5
	buyPrompt.MaxActivationDistance = 12
	buyPrompt.Parent = buyButton

	buyPrompt.Triggered:Connect(function(triggeringPlayer)
		if triggeringPlayer ~= player or not loadedPlayers[player.UserId] then return end

		local userId = player.UserId
		local credits = getCredits(player)

		if not credits or ownedBusinesses[userId] or credits.Value < BUSINESS_COST then
			return
		end

		credits.Value -= BUSINESS_COST
		ownedBusinesses[userId] = true
		businessLevels[userId] = 1

		createBusiness(plot, origin, 1)
		buyButton.Transparency = 1
		buyButton.CanCollide = false
		buyPrompt.Enabled = false

		updateSign(player)
		task.spawn(savePlayer, player)
	end)

	local upgradeButton = makePart(
		plot, "UpgradeBusinessButton", Vector3.new(12, 2, 8),
		origin + Vector3.new(20, 2, 35),
		Color3.fromRGB(120, 0, 255), Enum.Material.Neon
	)

	local upgradePrompt = Instance.new("ProximityPrompt")
	upgradePrompt.ActionText = "Upgrade Business"
	upgradePrompt.ObjectText = "Upgrade your headquarters"
	upgradePrompt.HoldDuration = 0.5
	upgradePrompt.MaxActivationDistance = 12
	upgradePrompt.Parent = upgradeButton

	local upgradeSign = addSign(
		plot, "UpgradeBusinessLabel",
		"UPGRADE HQ\nLEVEL 2: 500\nLEVEL 3: 1500",
		upgradeButton.Position + Vector3.new(0, 2.5, 0),
		Vector3.new(12, 4, 1)
	)

	upgradePrompt.Triggered:Connect(function(triggeringPlayer)
		if triggeringPlayer ~= player or not loadedPlayers[player.UserId] then return end

		local userId = player.UserId
		local credits = getCredits(player)
		local level = businessLevels[userId] or 0

		if not credits or not ownedBusinesses[userId] or level >= MAX_LEVEL then return end

		local cost = LEVEL_COSTS[level]
		if not cost or credits.Value < cost then return end

		credits.Value -= cost
		level += 1
		businessLevels[userId] = level

		createBusiness(plot, origin, level)

		local gui = upgradeSign:FindFirstChildOfClass("SurfaceGui")
		local label = gui and gui:FindFirstChildOfClass("TextLabel")

		if label then
			label.Text = level >= MAX_LEVEL
				and "MAX LEVEL REACHED"
				or ("UPGRADE HQ\nNEXT COST: " .. tostring(LEVEL_COSTS[level] or 0))
		end

		if level >= MAX_LEVEL then
			upgradePrompt.Enabled = false
		end

		updateSign(player)
		task.spawn(savePlayer, player)
	end)

	return plot
end

local function positionCharacter(player, character)
	local root = character:WaitForChild("HumanoidRootPart", 15)
	local humanoid = character:WaitForChild("Humanoid", 15)

	if not root or not humanoid then return end

	local origin = playerOrigins[player.UserId]
	if not origin or player.Parent ~= Players or not character.Parent then return end

	character:PivotTo(CFrame.new(origin + Vector3.new(0, 7, 12)))

	root.Anchored = false
	root.AssemblyLinearVelocity = Vector3.zero
	root.AssemblyAngularVelocity = Vector3.zero

	humanoid.WalkSpeed = 16
	humanoid.JumpPower = 50
	humanoid.AutoRotate = true
	humanoid.PlatformStand = false
	humanoid.Sit = false
	humanoid:ChangeState(Enum.HumanoidStateType.GettingUp)
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

	if player.Parent ~= Players then return end

	if typeof(data) ~= "table" then
		data = {
			Credits = STARTING_CREDITS,
			OwnsServer = false,
			BusinessLevel = 0
		}
	end

	local creditsValue = tonumber(data.Credits) or STARTING_CREDITS
	local ownsBusiness = data.OwnsServer == true
	local level = math.clamp(tonumber(data.BusinessLevel) or 0, 0, MAX_LEVEL)

	if ownsBusiness and level == 0 then
		level = 1
	elseif not ownsBusiness then
		level = 0
	end

	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	leaderstats.Parent = player

	local credits = Instance.new("IntValue")
	credits.Name = "Credits"
	credits.Value = math.max(0, math.floor(creditsValue))
	credits.Parent = leaderstats

	ownedBusinesses[player.UserId] = ownsBusiness
	businessLevels[player.UserId] = level

	createPlot(player)
	loadedPlayers[player.UserId] = true

	local plot = playerPlots[player.UserId]
	local origin = playerOrigins[player.UserId]

	if ownsBusiness then
		createBusiness(plot, origin, level)

		local buyButton = plot:FindFirstChild("BuyBusinessButton")
		if buyButton then
			buyButton.Transparency = 1
			buyButton.CanCollide = false
			local prompt = buyButton:FindFirstChildOfClass("ProximityPrompt")
			if prompt then prompt.Enabled = false end
		end

		local upgradeButton = plot:FindFirstChild("UpgradeBusinessButton")
		local prompt = upgradeButton and upgradeButton:FindFirstChildOfClass("ProximityPrompt")
		if level >= MAX_LEVEL and prompt then prompt.Enabled = false end
	end

	updateSign(player)
	credits.Changed:Connect(function()
		updateSign(player)
	end)

	player.CharacterAdded:Connect(function(character)
		task.spawn(function()
			positionCharacter(player, character)
		end)
	end)

	if player.Character then
		task.spawn(function()
			positionCharacter(player, player.Character)
		end)
	end

	print("Cyber City loaded for " .. player.Name)
end

Players.PlayerAdded:Connect(function(player)
	task.spawn(loadPlayer, player)
end)

for _, player in ipairs(Players:GetPlayers()) do
	task.spawn(loadPlayer, player)
end

task.spawn(function()
	while true do
		task.wait(INCOME_INTERVAL)

		for _, player in ipairs(Players:GetPlayers()) do
			local userId = player.UserId

			if loadedPlayers[userId] and ownedBusinesses[userId] then
				local credits = getCredits(player)

				if credits then
					local level = businessLevels[userId] or 1
					local income = LEVEL_INCOME[level] or LEVEL_INCOME[1]
					local multiplier = player:GetAttribute("CyberCityVIP") == true
						and VIP_MULTIPLIER or 1

					credits.Value += income * multiplier
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

Players.PlayerRemoving:Connect(function(player)
	savePlayer(player)

	local userId = player.UserId
	local plot = playerPlots[userId]
	if plot then plot:Destroy() end

	playerPlots[userId] = nil
	playerOrigins[userId] = nil
	ownedBusinesses[userId] = nil
	businessLevels[userId] = nil
	loadedPlayers[userId] = nil
	savingPlayers[userId] = nil
end)

game:BindToClose(function()
	local pending = 0

	for _, player in ipairs(Players:GetPlayers()) do
		if loadedPlayers[player.UserId] and not savingPlayers[player.UserId] then
			pending += 1
			task.spawn(function()
				savePlayer(player)
				pending -= 1
			end)
		end
	end

	local deadline = os.clock() + 25
	while pending > 0 and os.clock() < deadline do
		task.wait(0.1)
	end
end)

print("Cyber City Main system loaded.")
