import discord
import db

class PollButton(discord.ui.Button):
    def __init__(self, label, option_index, emoji):
        super().__init__(label=label, style=discord.ButtonStyle.primary, emoji=emoji)
        self.option_index = option_index
    
    async def callback(self, interaction: discord.Interaction):
        try:
            poll_view = self.view
            if not poll_view.poll_id:
                await interaction.response.send_message("Poll ID not found.", ephemeral=True)
                return
            
            from bson import ObjectId
            user_id = interaction.user.id
            
            # Get current poll data
            poll_data = db.dbmanager.polls_collection.find_one({"_id": ObjectId(poll_view.poll_id)})
            
            if not poll_data:
                await interaction.response.send_message("Poll not found.", ephemeral=True)
                return
            
            # Check if user already voted for this option
            current_votes = poll_data['votes'].get(str(self.option_index), [])
            
            if user_id in current_votes:
                await interaction.response.send_message("You have already voted for this option!", ephemeral=True)
                return
            
            # Remove user's vote from other options (allow vote changing)
            for option_idx in poll_data['votes']:
                if user_id in poll_data['votes'][option_idx]:
                    poll_data['votes'][option_idx].remove(user_id)
            
            # Add vote to selected option
            if str(self.option_index) not in poll_data['votes']:
                poll_data['votes'][str(self.option_index)] = []
            poll_data['votes'][str(self.option_index)].append(user_id)
            
            # Update database
            db.dbmanager.polls_collection.update_one(
                {"_id": ObjectId(poll_view.poll_id)},
                {"$set": {"votes": poll_data['votes']}}
            )
            
            # Update the embed
            embed = discord.Embed(
                title=f"📊 {poll_data['question']}",
                description="Click the buttons below to vote!",
                color=discord.Color.blue()
            )
            
            for i, option in enumerate(poll_data['options']):
                vote_count = len(poll_data['votes'].get(str(i), []))
                embed.add_field(
                    name=f"{i+1}️⃣ {option}",
                    value=f"{vote_count} votes",
                    inline=False
                )
            
            embed.set_footer(text=f"Poll created by {interaction.guild.get_member(poll_data['creator_id']).display_name if interaction.guild.get_member(poll_data['creator_id']) else 'Unknown'}")
            
            await interaction.response.edit_message(embed=embed, view=poll_view)
            
        except Exception as e:
            await interaction.response.send_message(f"Error voting: {e}", ephemeral=True)
