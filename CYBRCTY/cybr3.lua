
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")

local SaveStore = DataStoreService:GetDataStore("CyberCity_Save_V2")

local STARTING_CREDITS = 500
local BUSINESS_COST = 250
local INCOME_INTERVAL = 5
local AUTOSAVE_INTERVAL = 60
local MAX_LEVEL = 3

local LEVEL_COSTS = {
	[1] = 500,
	[2] = 1500
}

local LEVEL_INCOME = {
	[1] = 25,
	[2] = 75,
	[3] = 175
}

local playerPlots = {}
local playerOrigins = {}
local ownedBusinesses = {}
local businessLevels = {}
local loadedPlayers = {}
local savingPlayers = {}
local nextPlot = 0

local function makePart(parent, name, size, position, color, material)
	local part = Instance.new("Part")
	part.Name = name
	part.Size = size
	part.Position = position
	part.Anchored = true
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Color = color
	part.Material = material or Enum.Material.SmoothPlastic
	part.Parent = parent
	return part
end

local function addSign(part, text, textColor)
	local gui = Instance.new("BillboardGui")
	gui.Name = "SignGui"
	gui.Size = UDim2.new(0, 260, 0, 60)
	gui.StudsOffset = Vector3.new(0, 3, 0)
	gui.AlwaysOnTop = true
	gui.Parent = part

	local label = Instance.new("TextLabel")
	label.Name = "Label"
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.Text = text
	label.TextColor3 = textColor or Color3.fromRGB(0, 220, 255)
	label.TextScaled = true
	label.Font = Enum.Font.GothamBold
	label.TextStrokeTransparency = 0.35
	label.Parent = gui

	return label
end

local function getCredits(player)
	local stats = player:FindFirstChild("leaderstats")
	return stats and stats:FindFirstChild("Credits")
end

local function updateSign(part, text, color)
	local gui = part:FindFirstChild("SignGui")
	local label = gui and gui:FindFirstChild("Label")

	if label then
		label.Text = text
		if color then
			label.TextColor3 = color
		end
	end
end

local function createCityDecor(plot, origin)
	local cyan = Color3.fromRGB(0, 220, 255)
	local purple = Color3.fromRGB(150, 40, 255)
	local dark = Color3.fromRGB(18, 24, 48)
	local glass = Color3.fromRGB(25, 55, 95)

	local function buildTower(name, x, z, height, width, color)
		makePart(
			plot, name,
			Vector3.new(width, height, width),
			origin + Vector3.new(x, height / 2 + 0.6, z),
			dark, Enum.Material.Metal
		)

		makePart(
			plot, name .. " Roof Light",
			Vector3.new(width + 1, 0.4, width + 1),
			origin + Vector3.new(x, height + 0.8, z),
			color, Enum.Material.Neon
		)

		for floor = 1, math.floor(height / 5) do
			local y = floor * 5 + 0.6

			for _, side in ipairs({-1, 1}) do
				makePart(
					plot, name .. " Window",
					Vector3.new(width * 0.65, 1.8, 0.25),
					origin + Vector3.new(x, y, z + side * (width / 2 + 0.13)),
					glass, Enum.Material.Neon
				)
			end

			makePart(
				plot, name .. " Side Window",
				Vector3.new(0.25, 1.8, width * 0.65),
				origin + Vector3.new(x + width / 2 + 0.13, y, z),
				color, Enum.Material.Neon
			)
		end
	end

	buildTower("East Skyline Tower", 22, -21, 24, 8, cyan)
	buildTower("West Skyline Tower", -22, -21, 32, 9, purple)
	buildTower("East Front Tower", 22, 20, 18, 7, purple)
	buildTower("West Front Tower", -22, 20, 22, 7, cyan)

	for i = -2, 2 do
		makePart(
			plot, "Road Light Strip",
			Vector3.new(0.25, 0.15, 10),
			origin + Vector3.new(i * 3, 0.72, 0),
			i % 2 == 0 and cyan or purple,
			Enum.Material.Neon
		)
	end

	local welcome = makePart(
		plot, "CYBER CITY Welcome Sign",
		Vector3.new(16, 5, 1),
		origin + Vector3.new(0, 5, 27),
		dark, Enum.Material.Metal
	)
	addSign(welcome, "CYBER CITY", cyan)

	makePart(
		plot, "Welcome Sign Neon Frame",
		Vector3.new(17, 0.3, 1.3),
		origin + Vector3.new(0, 7.6, 27),
		cyan, Enum.Material.Neon
	)

	makePart(
		plot, "Welcome Sign Base",
		Vector3.new(1, 4, 1),
		origin + Vector3.new(-7, 2.5, 27),
		purple, Enum.Material.Neon
	)

	makePart(
		plot, "Welcome Sign Base",
		Vector3.new(1, 4, 1),
		origin + Vector3.new(7, 2.5, 27),
		cyan, Enum.Material.Neon
	)
end

local function createBusiness(plot, origin)
	local old = plot:FindFirstChild("ServerBusiness")
	if old then
		old:Destroy()
	end

	local level = businessLevels[plot:GetAttribute("OwnerUserId")] or 1
	local business = Instance.new("Folder")
	business.Name = "ServerBusiness"
	business.Parent = plot

	local cyan = Color3.fromRGB(0, 220, 255)
	local purple = Color3.fromRGB(155, 45, 255)
	local dark = Color3.fromRGB(15, 20, 42)

	local height = 10 + (level - 1) * 5
	local width = 14 + (level - 1) * 3

	makePart(
		business, "Server HQ",
		Vector3.new(width, height, 12 + (level - 1) * 2),
		origin + Vector3.new(0, height / 2 + 0.6, -8),
		dark, Enum.Material.Metal
	)

	makePart(
		business, "HQ Roof",
		Vector3.new(width + 1, 0.5, 13 + (level - 1) * 2),
		origin + Vector3.new(0, height + 0.85, -8),
		level == 3 and purple or cyan, Enum.Material.Neon
	)

	makePart(
		business, "Front Glass",
		Vector3.new(width * 0.65, height * 0.5, 0.25),
		origin + Vector3.new(0, height * 0.55, -1.87),
		cyan, Enum.Material.Glass
	)

	makePart(
		business, "Left Neon Panel",
		Vector3.new(0.3, height * 0.8, 9),
		origin + Vector3.new(-width / 2 - 0.15, height * 0.55, -8),
		purple, Enum.Material.Neon
	)

	makePart(
		business, "Right Neon Panel",
		Vector3.new(0.3, height * 0.8, 9),
		origin + Vector3.new(width / 2 + 0.15, height * 0.55, -8),
		cyan, Enum.Material.Neon
	)

	local sign = makePart(
		business, "Business Sign",
		Vector3.new(10, 1, 0.4),
		origin + Vector3.new(0, height * 0.75, -1.7),
		dark, Enum.Material.Metal
	)
	addSign(sign, level == 3 and "MEGATECH TOWER" or level == 2 and "ADVANCED DATA CENTER" or "CYBER SERVER HQ", cyan)
end

local function savePlayer(player)
	if not loadedPlayers[player.UserId] then
		return false
	end

	while savingPlayers[player.UserId] do
		task.wait(0.1)
		if not player.Parent then
			return false
		end
	end

	savingPlayers[player.UserId] = true

	local credits = getCredits(player)
	local data = {
		Credits = credits and credits.Value or STARTING_CREDITS,
		OwnsServer = ownedBusinesses[player.UserId] == true,
		BusinessLevel = businessLevels[player.UserId] or 1
	}

	local success = false

	for attempt = 1, 3 do
		local ok, result = pcall(function()
			return SaveStore:UpdateAsync("Player_" .. player.UserId, function(oldData)
				oldData = type(oldData) == "table" and oldData or {}
				oldData.Credits = data.Credits
				oldData.OwnsServer = data.OwnsServer
				oldData.BusinessLevel = data.BusinessLevel
				return oldData
			end)
		end)

		if ok then
			success = true
			break
		end

		warn("Save attempt " .. attempt .. " failed for " .. player.Name .. ": " .. tostring(result))
		task.wait(attempt * 2)
	end

	savingPlayers[player.UserId] = nil
	return success
end

local function createPlot(player)
	nextPlot += 1

	local index = nextPlot - 1
	local origin = Vector3.new((index % 4) * 90, 0, math.floor(index / 4) * 90)

	local plot = Instance.new("Folder")
	plot.Name = player.Name .. "_CyberPlot"
	plot:SetAttribute("OwnerUserId", player.UserId)
	plot.Parent = workspace

	playerPlots[player.UserId] = plot
	playerOrigins[player.UserId] = origin

	makePart(plot, "Plot Floor", Vector3.new(60, 1, 60), origin, Color3.fromRGB(22, 28, 45), Enum.Material.Metal)

	local cyan = Color3.fromRGB(0, 220, 255)
	local purple = Color3.fromRGB(150, 40, 255)

	makePart(plot, "Front Border", Vector3.new(60, 0.5, 0.5), origin + Vector3.new(0, 0.8, 30), cyan, Enum.Material.Neon)
	makePart(plot, "Back Border", Vector3.new(60, 0.5, 0.5), origin + Vector3.new(0, 0.8, -30), purple, Enum.Material.Neon)
	makePart(plot, "Left Border", Vector3.new(0.5, 0.5, 60), origin + Vector3.new(-30, 0.8, 0), purple, Enum.Material.Neon)
	makePart(plot, "Right Border", Vector3.new(0.5, 0.5, 60), origin + Vector3.new(30, 0.8, 0), cyan, Enum.Material.Neon)

	createCityDecor(plot, origin)

	local citySign = makePart(
		plot, "Player City Sign",
		Vector3.new(12, 2, 0.5),
		origin + Vector3.new(0, 2.5, 23),
		Color3.fromRGB(15, 20, 42), Enum.Material.Metal
	)
	addSign(citySign, player.Name .. "'S CITY", cyan)

	local buyButton = makePart(
		plot, "Purchase Button",
		Vector3.new(8, 1, 8),
		origin + Vector3.new(-10, 1.5, 8),
		cyan, Enum.Material.Neon
	)
	addSign(buyButton, "BUY SERVER HQ $" .. BUSINESS_COST, Color3.new(1, 1, 1))

	local buyPrompt = Instance.new("ProximityPrompt")
	buyPrompt.ActionText = "Buy Business"
	buyPrompt.ObjectText = "Server HQ - $" .. BUSINESS_COST
	buyPrompt.KeyboardKeyCode = Enum.KeyCode.E
	buyPrompt.HoldDuration = 0.5
	buyPrompt.MaxActivationDistance = 12
	buyPrompt.RequiresLineOfSight = false
	buyPrompt.Parent = buyButton

	local upgradeButton = makePart(
		plot, "Upgrade Button",
		Vector3.new(8, 1, 8),
		origin + Vector3.new(10, 1.5, 8),
		purple, Enum.Material.Neon
	)
	local upgradeSign = addSign(upgradeButton, "BUY SERVER FIRST", Color3.new(1, 1, 1))

	local upgradePrompt = Instance.new("ProximityPrompt")
	upgradePrompt.ActionText = "Upgrade Business"
	upgradePrompt.ObjectText = "Business Upgrade"
	upgradePrompt.KeyboardKeyCode = Enum.KeyCode.E
	upgradePrompt.HoldDuration = 0.5
	upgradePrompt.MaxActivationDistance = 12
	upgradePrompt.RequiresLineOfSight = false
	upgradePrompt.Parent = upgradeButton

	local function refreshButtons()
		local owns = ownedBusinesses[player.UserId] == true
		local level = businessLevels[player.UserId] or 1

		if owns then
			buyPrompt.Enabled = false
			buyPrompt.ActionText = "Already Purchased"
			updateSign(buyButton, "SERVER HQ OWNED", Color3.fromRGB(100, 255, 140))
		else
			buyPrompt.Enabled = true
			buyPrompt.ActionText = "Buy Business"
			updateSign(buyButton, "BUY SERVER HQ $" .. BUSINESS_COST, Color3.new(1, 1, 1))
		end

		if not owns then
			upgradePrompt.Enabled = false
			upgradePrompt.ActionText = "Buy Server First"
			updateSign(upgradeButton, "BUY SERVER FIRST", Color3.new(1, 1, 1))
		elseif level >= MAX_LEVEL then
			upgradePrompt.Enabled = false
			upgradePrompt.ActionText = "Maximum Level"
			updateSign(upgradeButton, "MAX LEVEL REACHED", Color3.fromRGB(100, 255, 140))
		else
			local cost = LEVEL_COSTS[level]
			upgradePrompt.Enabled = true
			upgradePrompt.ActionText = "Upgrade for $" .. cost
			updateSign(upgradeButton, "UPGRADE L" .. level .. " → L" .. (level + 1) .. " | $" .. cost, Color3.new(1, 1, 1))
		end
	end

	buyPrompt.Triggered:Connect(function(triggeringPlayer)
		if triggeringPlayer ~= player or not loadedPlayers[player.UserId] then
			return
		end

		if ownedBusinesses[player.UserId] then
			return
		end

		local credits = getCredits(player)
		if not credits or credits.Value < BUSINESS_COST then
			updateSign(buyButton, "NEED $" .. BUSINESS_COST, Color3.fromRGB(255, 90, 90))
			task.delay(2, refreshButtons)
			return
		end

		credits.Value -= BUSINESS_COST
		ownedBusinesses[player.UserId] = true
		businessLevels[player.UserId] = 1

		createBusiness(plot, origin)
		refreshButtons()
		task.spawn(savePlayer, player)
	end)

	upgradePrompt.Triggered:Connect(function(triggeringPlayer)
		if triggeringPlayer ~= player or not loadedPlayers[player.UserId] then
			return
		end

		if not ownedBusinesses[player.UserId] then
			return
		end

		local level = businessLevels[player.UserId] or 1
		if level >= MAX_LEVEL then
			refreshButtons()
			return
		end

		local cost = LEVEL_COSTS[level]
		local credits = getCredits(player)

		if not credits or credits.Value < cost then
			updateSign(upgradeButton, "NEED $" .. cost, Color3.fromRGB(255, 90, 90))
			task.delay(2, refreshButtons)
			return
		end

		credits.Value -= cost
		businessLevels[player.UserId] = level + 1

		createBusiness(plot, origin)
		refreshButtons()
		task.spawn(savePlayer, player)
	end)

	refreshButtons()

	if ownedBusinesses[player.UserId] then
		createBusiness(plot, origin)
	end

	return origin
end

local function loadPlayer(player)
	local creditsValue = STARTING_CREDITS
	local ownsServer = false
	local level = 1
	local loadedSuccessfully = false

	for attempt = 1, 3 do
		local ok, data = pcall(function()
			return SaveStore:GetAsync("Player_" .. player.UserId)
		end)

		if ok then
			loadedSuccessfully = true

			if type(data) == "table" then
				if type(data.Credits) == "number" then
					creditsValue = math.max(0, math.floor(data.Credits))
				end

				ownsServer = data.OwnsServer == true
				level = math.clamp(math.floor(tonumber(data.BusinessLevel) or 1), 1, MAX_LEVEL)
			end

			break
		end

		warn("Load attempt " .. attempt .. " failed for " .. player.Name .. ": " .. tostring(data))
		task.wait(attempt * 2)
	end

	if not player.Parent then
		return
	end

	if not loadedSuccessfully then
		warn("Could not load " .. player.Name .. "'s data. Session will not start to protect saved progress.")
		player:Kick("Your data could not load. Please rejoin in a moment so your progress stays safe.")
		return
	end

	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	stats.Parent = player

	local credits = Instance.new("IntValue")
	credits.Name = "Credits"
	credits.Value = creditsValue
	credits.Parent = stats

	ownedBusinesses[player.UserId] = ownsServer
	businessLevels[player.UserId] = ownsServer and level or 1
	loadedPlayers[player.UserId] = true

	local origin = createPlot(player)

	local function teleportCharacter(character)
		local root = character:WaitForChild("HumanoidRootPart", 10)
		if root and playerPlots[player.UserId] then
			root.CFrame = CFrame.new(origin + Vector3.new(0, 4, 17))
		end
	end

	if player.Character then
		task.spawn(teleportCharacter, player.Character)
	end

	player.CharacterAdded:Connect(teleportCharacter)
end

Players.PlayerAdded:Connect(function(player)
	task.spawn(loadPlayer, player)
end)

for _, player in ipairs(Players:GetPlayers()) do
	task.spawn(loadPlayer, player)
end

Players.PlayerRemoving:Connect(function(player)
	savePlayer(player)

	local plot = playerPlots[player.UserId]
	if plot then
		plot:Destroy()
	end

	playerPlots[player.UserId] = nil
	playerOrigins[player.UserId] = nil
	ownedBusinesses[player.UserId] = nil
	businessLevels[player.UserId] = nil
	loadedPlayers[player.UserId] = nil
	savingPlayers[player.UserId] = nil
end)

task.spawn(function()
	while true do
		task.wait(INCOME_INTERVAL)

		for _, player in ipairs(Players:GetPlayers()) do
			if loadedPlayers[player.UserId] and ownedBusinesses[player.UserId] then
				local credits = getCredits(player)
				local level = businessLevels[player.UserId] or 1

				if credits then
					credits.Value += LEVEL_INCOME[level] or LEVEL_INCOME[1]
				end
			end
		end
	end
end)

task.spawn(function()
	while true do
		task.wait(AUTOSAVE_INTERVAL)

		for _, player in ipairs(Players:GetPlayers()) do
			if loadedPlayers[player.UserId] then
				task.spawn(savePlayer, player)
			end
		end
	end
end)

game:BindToClose(function()
	local pending = 0

	for _, player in ipairs(Players:GetPlayers()) do
		if loadedPlayers[player.UserId] then
			pending += 1

			task.spawn(function()
				savePlayer(player)
				pending -= 1
			end)
		end
	end

	local startTime = os.clock()

	while pending > 0 and os.clock() - startTime < 25 do
		task.wait(0.1)
	end
end)