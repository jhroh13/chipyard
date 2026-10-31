package chipyard

import org.chipsalliance.cde.config.Config
import freechips.rocketchip.tile.OpcodeSet

/** Four RV64 Rockets, each with 8 KiB L1I/L1D and a private accumulator RoCC.
  * The shared inclusive L2 is 64 KiB. All caches use 64-byte lines.
  */
class QuadRocketRoCCConfig extends Config(
  new chipyard.config.WithAccumulatorRoCC(OpcodeSet.custom0) ++
  new freechips.rocketchip.rocket.WithL1ICacheSets(64) ++
  new freechips.rocketchip.rocket.WithL1ICacheWays(2) ++
  new freechips.rocketchip.rocket.WithL1DCacheSets(64) ++
  new freechips.rocketchip.rocket.WithL1DCacheWays(2) ++
  new freechips.rocketchip.subsystem.WithInclusiveCache(nWays = 4, capacityKB = 64) ++
  new freechips.rocketchip.subsystem.WithNBanks(1) ++
  new freechips.rocketchip.rocket.WithNHugeCores(4) ++
  new chipyard.config.AbstractConfig)
